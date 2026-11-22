from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.managed_keys import STATUS_FAILED, STATUS_OK
from app.models import Provider, RoutePolicy
from app.providers.catalogue import (
    PROVIDERS,
    PUBLIC_TEXT_TASKS,
    TASK_LABELS,
    AiTask,
    model_for,
    models_for,
    spec_for,
    supports,
)
from app.services import managed_secrets

KEY_ABSENT = "ABSENT"
KEY_UNTESTED = "UNTESTED"
KEY_PASSING = "PASSING"
KEY_FAILING = "FAILING"


def key_state(described: dict[str, Any] | None) -> tuple[str, Any, str | None]:
    if described is None or not described.get("configured"):
        return KEY_ABSENT, None, None
    status_text = described.get("lastStatus")
    if status_text == STATUS_OK:
        return KEY_PASSING, described.get("lastCheckedAt"), None
    if status_text == STATUS_FAILED:
        return KEY_FAILING, described.get("lastCheckedAt"), described.get("lastError")
    return KEY_UNTESTED, None, None


def frozen_reason(state: str, key_label: str, error: str | None) -> str | None:
    if state == KEY_ABSENT:
        return f"No {key_label} key has been added. Add it under API keys, then test it."
    if state == KEY_UNTESTED:
        return f"The {key_label} key has not been tested yet. Press Test."
    if state == KEY_FAILING:
        return f"The last test of the {key_label} key failed: {error or 'the provider refused it'}."
    return None


def freeze_unrankable(entries: list[dict[str, Any]], rankable: set[str]) -> list[dict[str, Any]]:
    passing = [e for e in entries if e["provider"] in rankable]
    frozen = [e for e in entries if e["provider"] not in rankable]
    return passing + frozen


async def provider_rows(session: AsyncSession) -> dict[str, Provider]:
    return {row.name: row for row in (await session.execute(select(Provider))).scalars().all()}


async def key_states(session: AsyncSession) -> dict[str, dict[str, Any]]:
    described = {entry["key"]: entry for entry in await managed_secrets.list_managed_secrets(session)}
    states: dict[str, dict[str, Any]] = {}
    for provider, spec in PROVIDERS.items():
        entry = described.get(spec.managed_key)
        state, tested_at, error = key_state(entry)
        states[provider.value] = {
            "keyName": spec.managed_key,
            "keyLabel": spec.label,
            "configured": bool(entry and entry.get("configured")),
            "keyState": state,
            "rankable": state == KEY_PASSING,
            "frozenReason": frozen_reason(state, spec.label, error),
            "testedAt": tested_at,
            "testError": error,
        }
    return states


def provider_rows_for_routing(
    catalogue_rows: list[dict[str, Any]], states: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    out = []
    for entry in catalogue_rows:
        state = states.get(entry["provider"], {})
        out.append(
            {
                "id": entry["provider"],
                "name": entry["label"],
                "keyName": entry["managedKey"],
                "keyState": state.get("keyState", KEY_ABSENT),
                "publicTextOnly": entry["dataClass"] == "PUBLIC_TEXT_ONLY",
                "models": [
                    {"id": model["id"], "label": model["label"], "tasks": model["tasks"]}
                    for model in entry["models"]
                ],
            }
        )
    return out


async def task_state(
    session: AsyncSession, task: AiTask, *, normalised: bool = False, note: str | None = None
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(RoutePolicy, Provider)
            .join(Provider, Provider.id == RoutePolicy.providerId)
            .where(RoutePolicy.task == task.value)
            .order_by(RoutePolicy.ordinal)
        )
    ).all()
    states = await key_states(session)
    routes = []
    for route, provider in rows:
        spec = spec_for(provider.name)
        model = model_for(provider.name, route.model)
        state = states.get(provider.name, {})
        routes.append(
            {
                "ordinal": route.ordinal,
                "provider": provider.name,
                "providerLabel": spec.label if spec else provider.name,
                "model": route.model,
                "modelLabel": model.label if model else route.model,
                "enabled": route.enabled and provider.enabled,
                "maxOutputTokens": route.maxOutputTokens,
                "temperature": route.temperature,
                "supported": supports(provider.name, route.model, task),
                "dataClass": provider.dataClass,
                **state,
            }
        )
    effective = [
        f"{r['provider']}:{r['model']}" for r in routes if r["enabled"] and r["supported"] and r["configured"]
    ]
    verified = [
        f"{r['provider']}:{r['model']}" for r in routes if r["enabled"] and r["supported"] and r["rankable"]
    ]
    available = [
        {
            "provider": spec.provider.value,
            "model": model.id,
            "label": model.label,
            "priceVerified": model.price_verified,
        }
        for spec in PROVIDERS.values()
        for model in models_for(spec.provider, task)
        if supports(spec.provider, model.id, task)
    ]
    return {
        "task": task.value,
        "label": TASK_LABELS.get(task, task.value),
        "publicText": task in PUBLIC_TEXT_TASKS,
        "routes": routes,
        "effectiveChain": effective,
        "verifiedChain": verified,
        "normalised": normalised,
        "normalisedNote": note,
        "availableModels": available,
    }


def validate_entries(task: AiTask, entries: list[dict[str, Any]]) -> str | None:
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        provider = str(entry["provider"]).upper()
        if spec_for(provider) is None:
            return f"unknown provider {entry['provider']!r}"
        if not supports(provider, entry["model"], task):
            return f"{provider} {entry['model']} cannot run {task.value}"
        pair = (provider, entry["model"])
        if pair in seen:
            return f"{provider} {entry['model']} is listed twice"
        seen.add(pair)
    return None


async def save_order(
    session: AsyncSession, task: AiTask, entries: list[dict[str, Any]], actor_id: Any
) -> None:
    providers = await provider_rows(session)
    kept_params = {
        (route.providerId, route.model): dict(route.params or {})
        for route in (
            await session.execute(select(RoutePolicy).where(RoutePolicy.task == task.value))
        ).scalars()
    }
    await session.execute(delete(RoutePolicy).where(RoutePolicy.task == task.value))
    for ordinal, entry in enumerate(entries, start=1):
        provider = providers.get(str(entry["provider"]).upper())
        if provider is None:
            continue
        session.add(
            RoutePolicy(
                task=task.value,
                ordinal=ordinal,
                providerId=provider.id,
                model=entry["model"],
                maxOutputTokens=entry.get("maxOutputTokens"),
                temperature=entry.get("temperature"),
                enabled=bool(entry.get("enabled", True)),
                params=kept_params.get((provider.id, entry["model"]), {}),
                updatedById=actor_id,
            )
        )
    await session.flush()
