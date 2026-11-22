from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.secrets import require_step_up
from app.core import daily_allowances
from app.core.db import get_session
from app.core.deps import require
from app.core.errors import InvalidInput
from app.core.roles import Capability
from app.models import User
from app.providers.catalogue import ROUTABLE_TASKS, AiTask, catalogue, spec_for, task_of
from app.schemas.admin import AppSettingsUpdate, RouteOrderUpdate, RouteTestRequest, VoiceSettingsUpdate
from app.services import app_settings, audit, managed_secrets, route_policy

router = APIRouter(prefix="/settings", tags=["settings"])

routing_manager = require(Capability.MANAGE_ROUTING)
ceiling_manager = require(Capability.MANAGE_CEILINGS)
DAILY_ALLOWANCES_KEY = "QuotaPolicy.perDay"


def _task_or_404(task: str) -> AiTask:
    resolved = task_of(task)
    if resolved is None or resolved not in ROUTABLE_TASKS:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Unknown task {task!r}. Routable tasks: {', '.join(t.value for t in ROUTABLE_TASKS)}",
        )
    return resolved


def _join(names: list[str]) -> str:
    if len(names) <= 1:
        return names[0] if names else ""
    return f"{', '.join(names[:-1])} and {names[-1]}"


@router.get("/ai-catalogue")
async def ai_catalogue(_: User = Depends(routing_manager)) -> dict[str, Any]:
    return {"providers": catalogue(), "tasks": [t.value for t in ROUTABLE_TASKS]}


@router.get("/ai-routing")
async def get_all_routing(
    _: User = Depends(routing_manager), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    return {
        "tasks": [await route_policy.task_state(session, task) for task in ROUTABLE_TASKS],
        "providers": route_policy.provider_rows_for_routing(
            catalogue(), await route_policy.key_states(session)
        ),
    }


@router.get("/ai-routing/{task}")
async def get_task_routing(
    task: str, _: User = Depends(routing_manager), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    return await route_policy.task_state(session, _task_or_404(task))


@router.put("/ai-routing/{task}")
async def update_task_routing(
    task: str,
    payload: RouteOrderUpdate,
    actor: User = Depends(routing_manager),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    resolved = _task_or_404(task)
    entries = [entry.model_dump() | {"provider": entry.provider.upper()} for entry in payload.routes]
    problem = route_policy.validate_entries(resolved, entries)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"routes: {problem}")
    states = await route_policy.key_states(session)
    rankable = {provider for provider, state in states.items() if state["rankable"]}
    ranked = route_policy.freeze_unrankable(entries, rankable)
    sank = [
        states[e["provider"]]["keyLabel"]
        for e in entries
        if e["provider"] not in rankable and ranked.index(e) > entries.index(e)
    ]
    note = None
    if sank:
        names = sorted(set(sank))
        verb = "has" if len(names) == 1 else "have"
        note = f"{_join(names)} {verb} not passed a key test, so moved below the routes that have. Test and reorder."
    await route_policy.save_order(session, resolved, ranked, actor.id)
    await audit.record(
        session,
        action="routing.updated",
        actor=actor,
        target_type="RoutePolicy",
        target_id=resolved.value,
        detail={"routes": [f"{e['provider']}:{e['model']}" for e in ranked]},
    )
    await session.commit()
    return await route_policy.task_state(session, resolved, normalised=bool(sank), note=note)


@router.post("/ai-routing/{task}/test")
async def test_task_provider(
    task: str,
    payload: RouteTestRequest,
    actor: User = Depends(routing_manager),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    resolved = _task_or_404(task)
    spec = spec_for(payload.provider)
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown provider {payload.provider!r}")
    result = await managed_secrets.test_secret(session, spec.managed_key)
    await audit.record(
        session,
        action="routing.provider_tested",
        actor=actor,
        target_type="ManagedSecret",
        target_id=spec.managed_key,
        detail={"status": result["lastStatus"], "task": resolved.value},
    )
    await session.commit()
    return await route_policy.task_state(session, resolved)


@router.get("/voice")
async def get_voice(
    _: User = Depends(routing_manager), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    return app_settings.voice_view(await app_settings.load_all(session))


@router.put("/voice")
async def update_voice(
    payload: VoiceSettingsUpdate,
    actor: User = Depends(routing_manager),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    changes = app_settings.voice_changes(payload.model_dump())
    for key, value in changes.items():
        await app_settings.set_value(session, key, value, actor.id)
    if changes:
        await audit.record(
            session,
            action="settings.voice_updated",
            actor=actor,
            target_type="AppSetting",
            detail={"keys": sorted(changes)},
        )
    await session.commit()
    return app_settings.voice_view(await app_settings.load_all(session))


async def _budget_view(session: AsyncSession) -> dict[str, Any]:
    allowances = await daily_allowances.load_daily_allowances(session)
    return {
        **app_settings.public_view(await app_settings.load_all(session)),
        "dailyAllowances": allowances.view(),
    }


@router.get("/ai-budget")
async def get_budget(
    _: User = Depends(ceiling_manager), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    return await _budget_view(session)


@router.put("/ai-budget")
async def update_budget(
    payload: AppSettingsUpdate,
    actor: User = Depends(ceiling_manager),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await require_step_up(session, actor, payload.twoFactorCode)
    try:
        changed = await _saved_budget(session, payload, actor)
    except InvalidInput as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from None
    if changed:
        await audit.record(
            session,
            action="settings.ai_budget_updated",
            actor=actor,
            target_type="AppSetting",
            detail={"keys": changed},
        )
    await session.commit()
    daily_allowances.invalidate()
    return await _budget_view(session)


async def _saved_budget(session: AsyncSession, payload: AppSettingsUpdate, actor: User) -> list[str]:
    update = app_settings.sent_budget_fields(payload.model_dump(), payload.model_fields_set)
    changes = app_settings.budget_changes(update, await app_settings.load_all(session))
    if payload.dailyAllowances is not None:
        await daily_allowances.save_daily_allowances(session, payload.dailyAllowances)
    for key, value in changes.items():
        await app_settings.set_value(session, key, value, actor.id)
    allowances = [DAILY_ALLOWANCES_KEY] if payload.dailyAllowances is not None else []
    return sorted([*changes, *allowances])
