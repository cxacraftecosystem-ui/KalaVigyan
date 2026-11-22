from __future__ import annotations

import hmac
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.key_catalogue import MANAGED_KEYS, ManagedKey, format_problem, is_managed
from app.core.key_checks import KEY_CHECK_SECONDS, KeyCheck, KeyVerdict
from app.core.managed_keys import (
    STATUS_FAILED,
    STATUS_OK,
    STATUS_UNKNOWN,
    decrypt,
    encrypt,
    env_value,
    fingerprint,
    get_secret,
    invalidate,
    peek_secret,
    refresh_if_stale,
)
from app.models import ManagedSecret, SecretTestResult, User
from app.providers import anthropic_p, elevenlabs_key, gemini_p, openai_p
from app.providers.presets import BY_PRESET
from app.sources.scholarly import core_works, elsevier, openalex, semantic_scholar, springer_nature
from app.sources.web import brave

__all__ = [
    "KEY_CHECKS",
    "SOURCE_DATABASE",
    "SOURCE_ENVIRONMENT",
    "SOURCE_UNSET",
    "delete_secret",
    "describe_secret",
    "get_secret",
    "hint",
    "is_managed",
    "key_verdict",
    "list_managed_secrets",
    "set_secret",
    "test_secret",
]

logger = logging.getLogger(__name__)

SOURCE_DATABASE = "database"
SOURCE_ENVIRONMENT = "environment"
SOURCE_UNSET = "unset"
SHORTEST_HIDDEN_KEY = 8

UNDECRYPTABLE_ERROR = (
    "The saved key can no longer be read. Enter it again; the default value is used meanwhile."
)
NOT_CONFIGURED = "Not configured"
NO_CHECK = "This key has no check yet."
UNTESTED = "The key couldn't be tested. Try again."

KEY_CHECKS: Mapping[str, KeyCheck] = MappingProxyType(
    {
        "GEMINI_API_KEY": gemini_p.check_key,
        "ANTHROPIC_API_KEY": anthropic_p.check_key,
        "OPENAI_API_KEY": openai_p.key_check_at(BY_PRESET["openai"]["base_url"]),
        "DEEPSEEK_API_KEY": openai_p.key_check_at(BY_PRESET["deepseek"]["base_url"]),
        "ELEVENLABS_API_KEY": elevenlabs_key.check_key,
        "BRAVE_SEARCH_API_KEY": brave.check_key,
        "OPENALEX_API_KEY": openalex.check_key,
        "SEMANTIC_SCHOLAR_API_KEY": semantic_scholar.check_key,
        "CORE_API_KEY": core_works.check_key,
        "SPRINGER_NATURE_API_KEY": springer_nature.check_key,
        "ELSEVIER_API_KEY": elsevier.check_key,
    }
)


def hint(value: str | None) -> str | None:
    if not value:
        return None
    return value[-4:] if len(value) > SHORTEST_HIDDEN_KEY else "…"


async def key_verdict(spec: ManagedKey, value: str) -> KeyVerdict:
    if spec.format is not None:
        problem = format_problem(spec.format, value)
        return KeyVerdict(ok=problem is None, error=problem)
    check = KEY_CHECKS.get(spec.key)
    if check is None:
        return KeyVerdict(ok=False, error=NO_CHECK)
    try:
        async with httpx.AsyncClient(timeout=KEY_CHECK_SECONDS) as client:
            verdict = await check(client, value)
    except Exception as error:
        logger.warning("key check failed", extra={"error": type(error).__name__})
        return KeyVerdict(ok=False, error=UNTESTED)
    if verdict.error and len(value) >= SHORTEST_HIDDEN_KEY:
        return KeyVerdict(ok=verdict.ok, error=verdict.error.replace(value, "***"))
    return verdict


def _last_verdict(
    row: ManagedSecret | None, verdict: SecretTestResult | None, environment: str | None
) -> tuple[str, datetime | None, str | None]:
    if row is not None:
        return row.lastStatus, row.lastCheckedAt, row.lastError
    if (
        verdict is not None
        and environment
        and hmac.compare_digest(verdict.fingerprint, fingerprint(environment))
    ):
        return verdict.status, verdict.checkedAt, verdict.error
    return STATUS_UNKNOWN, None, None


def _describe(
    spec: ManagedKey, row: ManagedSecret | None, verdict: SecretTestResult | None, updated_by: User | None
) -> dict[str, Any]:
    environment = env_value(spec.key)
    readable = row is not None and decrypt(row.valueEnc) is not None
    source = SOURCE_DATABASE if readable else (SOURCE_ENVIRONMENT if environment else SOURCE_UNSET)
    last = _last_verdict(row, verdict, environment)
    if row is not None and not readable:
        last = (STATUS_FAILED, last[1], UNDECRYPTABLE_ERROR)
    return {
        "key": spec.key,
        "label": spec.label,
        "description": spec.description,
        "group": spec.group,
        "formatOnly": spec.format_only,
        "configured": readable or bool(environment),
        "source": source,
        "overrideUnreadable": row is not None and not readable,
        "hint": row.hint if readable and row is not None else hint(environment),
        "lastStatus": last[0],
        "lastCheckedAt": last[1].isoformat() if last[1] else None,
        "lastError": last[2],
        "updatedBy": (updated_by.name or updated_by.email) if updated_by else None,
        "updatedAt": row.updatedAt.isoformat() if row is not None and row.updatedAt else None,
    }


async def _state(
    session: AsyncSession,
) -> tuple[dict[str, ManagedSecret], dict[str, SecretTestResult], dict[Any, User]]:
    rows = {row.key: row for row in (await session.execute(select(ManagedSecret))).scalars().all()}
    verdicts = {row.key: row for row in (await session.execute(select(SecretTestResult))).scalars().all()}
    ids = {row.updatedById for row in rows.values() if row.updatedById}
    people = {}
    if ids:
        people = {
            u.id: u for u in (await session.execute(select(User).where(User.id.in_(ids)))).scalars().all()
        }
    return rows, verdicts, people


async def list_managed_secrets(session: AsyncSession) -> list[dict[str, Any]]:
    rows, verdicts, people = await _state(session)
    return [
        _describe(
            spec, rows.get(key), verdicts.get(key), people.get(getattr(rows.get(key), "updatedById", None))
        )
        for key, spec in MANAGED_KEYS.items()
    ]


async def describe_secret(session: AsyncSession, key: str) -> dict[str, Any]:
    rows, verdicts, people = await _state(session)
    row = rows.get(key)
    return _describe(MANAGED_KEYS[key], row, verdicts.get(key), people.get(getattr(row, "updatedById", None)))


async def set_secret(session: AsyncSession, key: str, value: str, updated_by_id: Any) -> dict[str, Any]:
    plaintext = value.strip()
    spec = MANAGED_KEYS[key]
    values = {
        "valueEnc": encrypt(plaintext),
        "hint": hint(plaintext),
        "description": spec.description,
        "lastStatus": STATUS_UNKNOWN,
        "lastCheckedAt": None,
        "lastError": None,
        "updatedById": updated_by_id,
    }
    await session.execute(
        insert(ManagedSecret)
        .values(key=key, **values)
        .on_conflict_do_update(index_elements=[ManagedSecret.key], set_=values)
    )
    await session.commit()
    invalidate()
    return await describe_secret(session, key)


async def delete_secret(session: AsyncSession, key: str) -> dict[str, Any]:
    await session.execute(delete(ManagedSecret).where(ManagedSecret.key == key))
    await session.commit()
    invalidate()
    return await describe_secret(session, key)


async def test_secret(session: AsyncSession, key: str) -> dict[str, Any]:
    spec = MANAGED_KEYS[key]
    await refresh_if_stale(session, force=True)
    value = peek_secret(key)
    checked_at = datetime.now(UTC)
    verdict = KeyVerdict(ok=False, error=NOT_CONFIGURED) if not value else await key_verdict(spec, value)
    await _record_verdict(session, key, value, verdict, checked_at)
    await session.commit()
    described = await describe_secret(session, key)
    described["lastStatus"] = STATUS_OK if verdict.ok else STATUS_FAILED
    described["lastCheckedAt"] = checked_at.isoformat()
    described["lastError"] = None if verdict.ok else verdict.error
    return described


async def _record_verdict(
    session: AsyncSession, key: str, value: str | None, verdict: KeyVerdict, checked_at: datetime
) -> None:
    status_text = STATUS_OK if verdict.ok else STATUS_FAILED
    error = None if verdict.ok else verdict.error
    row = (await session.execute(select(ManagedSecret).where(ManagedSecret.key == key))).scalar_one_or_none()
    if row is not None and decrypt(row.valueEnc) is not None:
        row.lastStatus, row.lastCheckedAt, row.lastError = status_text, checked_at, error
        return
    if not value:
        return
    payload = {
        "status": status_text,
        "checkedAt": checked_at,
        "error": error,
        "fingerprint": fingerprint(value),
    }
    await session.execute(
        insert(SecretTestResult)
        .values(key=key, **payload)
        .on_conflict_do_update(index_elements=[SecretTestResult.key], set_=payload)
    )
