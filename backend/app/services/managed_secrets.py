import base64
import hashlib
import hmac
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import ManagedSecret, SecretTestResult, User

logger = logging.getLogger(__name__)

_HKDF_INFO = b"kalavigyan/managed-secrets/v1"
_FINGERPRINT_HKDF_INFO = b"kalavigyan/secret-verdict-fingerprint/v1"
_CACHE_TTL_SECONDS = 30.0
_PROBE_TIMEOUT_SECONDS = 6.0

STATUS_UNKNOWN = "UNKNOWN"
STATUS_OK = "OK"
STATUS_FAILED = "FAILED"

SOURCE_DATABASE = "database"
SOURCE_ENVIRONMENT = "environment"
SOURCE_UNSET = "unset"

UNDECRYPTABLE_ERROR = (
    "The saved key can no longer be read. Enter it again; the default value is used meanwhile."
)


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    settings = get_settings()
    configured = (settings.secrets_encryption_key or "").strip()
    if configured:
        with suppress(Exception):
            return Fernet(configured.encode("utf-8"))
        return Fernet(_derive_fernet_key(configured))
    return Fernet(_derive_fernet_key(settings.jwt_secret))


def _derive_fernet_key(source: str) -> bytes:
    raw = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(
        source.encode("utf-8")
    )
    return base64.urlsafe_b64encode(raw)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken, ValueError, TypeError:
        return None


@lru_cache(maxsize=1)
def _fingerprint_pepper() -> bytes:
    settings = get_settings()
    source = (settings.secrets_encryption_key or "").strip() or settings.jwt_secret
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_FINGERPRINT_HKDF_INFO).derive(
        source.encode("utf-8")
    )


def fingerprint(value: str) -> str:
    return hmac.new(_fingerprint_pepper(), value.encode("utf-8"), hashlib.sha256).hexdigest()


Probe = Callable[[str], Awaitable[tuple[bool, str | None]]]


async def _probe_http(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> tuple[bool, str | None]:
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT_SECONDS) as client:
            response = await client.request(method, url, headers=headers or {}, params=params or {})
    except httpx.TimeoutException:
        return False, "The provider didn't answer in time. Try again."
    except httpx.HTTPError as exc:
        logger.warning("key probe network error", extra={"error": type(exc).__name__})
        return False, "The provider couldn't be reached. Try again."
    if response.is_success:
        return True, None
    if response.status_code in {401, 403}:
        return False, "The provider didn't accept this key."
    if response.status_code == 429:
        return False, "The key works, but it has reached its usage limit. Try again later."
    return False, "The provider had a problem checking this key. Try again later."


def _bearer(url: str) -> Probe:
    async def probe(value: str) -> tuple[bool, str | None]:
        return await _probe_http("GET", url, headers={"Authorization": f"Bearer {value}"})

    return probe


def _header(
    url: str, name: str, params: dict[str, str] | None = None, extra: dict[str, str] | None = None
) -> Probe:
    async def probe(value: str) -> tuple[bool, str | None]:
        return await _probe_http("GET", url, headers={name: value, **(extra or {})}, params=params)

    return probe


def _query(url: str, name: str, params: dict[str, str] | None = None) -> Probe:
    async def probe(value: str) -> tuple[bool, str | None]:
        return await _probe_http("GET", url, params={**(params or {}), name: value})

    return probe


def _format(min_length: int = 8, suffix: str | None = None, hint: str = "") -> Probe:
    async def probe(value: str) -> tuple[bool, str | None]:
        candidate = value.strip()
        if len(candidate) < min_length or (suffix and not candidate.endswith(suffix)):
            return False, hint or "This doesn't look like a valid value."
        return True, None

    return probe


@dataclass(frozen=True)
class ManagedKey:
    key: str
    label: str
    description: str
    group: str
    probe: Probe
    format_only: bool = False

    @property
    def settings_attr(self) -> str:
        return self.key.lower()


MANAGED_KEYS: dict[str, ManagedKey] = {
    spec.key: spec
    for spec in (
        ManagedKey(
            "GEMINI_API_KEY",
            "Google Gemini",
            "Planner, reader, voice turns, embeddings, images and video.",
            "AI",
            _header(
                "https://generativelanguage.googleapis.com/v1beta/models", "x-goog-api-key", {"pageSize": "1"}
            ),
        ),
        ManagedKey(
            "ANTHROPIC_API_KEY",
            "Anthropic Claude",
            "Answer composer and evaluation judge.",
            "AI",
            _header(
                "https://api.anthropic.com/v1/models", "x-api-key", extra={"anthropic-version": "2023-06-01"}
            ),
        ),
        ManagedKey(
            "OPENAI_API_KEY",
            "OpenAI",
            "Fallback route for planning, composing and voice turns.",
            "AI",
            _bearer("https://api.openai.com/v1/models"),
        ),
        ManagedKey(
            "DEEPSEEK_API_KEY",
            "DeepSeek",
            "Public-text reading and extraction only.",
            "AI",
            _bearer("https://api.deepseek.com/models"),
        ),
        ManagedKey(
            "ELEVENLABS_API_KEY",
            "ElevenLabs",
            "Voice conversation: speech-to-text and text-to-speech.",
            "Voice",
            _header("https://api.elevenlabs.io/v1/user", "xi-api-key"),
        ),
        ManagedKey(
            "VOYAGE_API_KEY",
            "Voyage AI",
            "Reranks stored facts for answers.",
            "AI",
            _format(16),
            format_only=True,
        ),
        ManagedKey(
            "BRAVE_SEARCH_API_KEY",
            "Brave Search",
            "Web search fallback when SearXNG returns too little.",
            "Search",
            _header(
                "https://api.search.brave.com/res/v1/web/search",
                "X-Subscription-Token",
                {"q": "kalamkari", "count": "1"},
            ),
        ),
        ManagedKey("EXA_API_KEY", "Exa", "Deep research search.", "Search", _format(16), format_only=True),
        ManagedKey(
            "TAVILY_API_KEY", "Tavily", "Deep research search.", "Search", _format(16), format_only=True
        ),
        ManagedKey(
            "OPENALEX_API_KEY",
            "OpenAlex",
            "Scholarly works metadata and open-access links.",
            "Scholarly",
            _query("https://api.openalex.org/works", "api_key", {"per-page": "1"}),
        ),
        ManagedKey(
            "SEMANTIC_SCHOLAR_API_KEY",
            "Semantic Scholar",
            "Scholarly search and abstracts.",
            "Scholarly",
            _header(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                "x-api-key",
                {"query": "mordant", "limit": "1"},
            ),
        ),
        ManagedKey(
            "CORE_API_KEY",
            "CORE",
            "Open-access full text.",
            "Scholarly",
            _bearer("https://api.core.ac.uk/v3/search/works?q=mordant&limit=1"),
        ),
        ManagedKey(
            "SPRINGER_NATURE_API_KEY",
            "Springer Nature",
            "Open-access and TDM full text.",
            "Scholarly",
            _query("https://api.springernature.com/openaccess/json", "api_key", {"q": "dye", "p": "1"}),
        ),
        ManagedKey(
            "ELSEVIER_API_KEY",
            "Elsevier",
            "ScienceDirect and Scopus text mining.",
            "Scholarly",
            _header(
                "https://api.elsevier.com/content/search/scopus",
                "X-ELS-APIKey",
                {"query": "mordant", "count": "1"},
            ),
        ),
        ManagedKey(
            "ELSEVIER_INSTTOKEN",
            "Elsevier institution token",
            "Institutional entitlement for Elsevier.",
            "Scholarly",
            _format(8),
            format_only=True,
        ),
        ManagedKey(
            "WILEY_TDM_TOKEN",
            "Wiley TDM",
            "Wiley text and data mining.",
            "Scholarly",
            _format(8),
            format_only=True,
        ),
        ManagedKey(
            "DATA_GOV_IN_API_KEY",
            "data.gov.in",
            "Government open datasets.",
            "Data",
            _format(16),
            format_only=True,
        ),
        ManagedKey(
            "GOOGLE_CLIENT_ID",
            "Google sign-in client ID",
            "Web client ID for Google sign-in.",
            "Sign-in",
            _format(30, ".apps.googleusercontent.com", "This should end in .apps.googleusercontent.com."),
            format_only=True,
        ),
    )
}


def is_managed(key: str) -> bool:
    return key in MANAGED_KEYS


_overrides: dict[str, str] = {}
_loaded_at = 0.0


def invalidate() -> None:
    global _loaded_at
    _loaded_at = 0.0


def _cache_is_fresh() -> bool:
    return _loaded_at > 0.0 and (time.monotonic() - _loaded_at) < _CACHE_TTL_SECONDS


async def refresh_if_stale(session: AsyncSession, force: bool = False) -> None:
    global _overrides, _loaded_at
    if not force and _cache_is_fresh():
        return
    try:
        rows = (await session.execute(select(ManagedSecret))).scalars().all()
    except Exception as exc:
        logger.warning(
            "could not load managed secrets; using environment values", extra={"error": type(exc).__name__}
        )
        return
    fresh: dict[str, str] = {}
    for row in rows:
        if row.key not in MANAGED_KEYS:
            continue
        plaintext = decrypt(row.valueEnc)
        if plaintext is None:
            logger.error("managed secret could not be decrypted", extra={"key": row.key})
            continue
        fresh[row.key] = plaintext
    _overrides = fresh
    _loaded_at = time.monotonic()


def env_value(key: str) -> str | None:
    spec = MANAGED_KEYS.get(key)
    if spec is None:
        return None
    value = getattr(get_settings(), spec.settings_attr, None)
    text = str(value).strip() if value is not None else ""
    return text or None


def peek_secret(key: str) -> str | None:
    return _overrides.get(key) or env_value(key)


async def get_secret(session: AsyncSession, key: str) -> str | None:
    await refresh_if_stale(session)
    return peek_secret(key)


def hint(value: str | None) -> str | None:
    if not value:
        return None
    return value[-4:] if len(value) > 8 else "…"


def _describe(
    spec: ManagedKey, row: ManagedSecret | None, verdict: SecretTestResult | None, updated_by: User | None
) -> dict[str, Any]:
    environment = env_value(spec.key)
    readable = row is not None and decrypt(row.valueEnc) is not None
    source = SOURCE_DATABASE if readable else (SOURCE_ENVIRONMENT if environment else SOURCE_UNSET)
    if row is not None:
        last = (row.lastStatus, row.lastCheckedAt, row.lastError)
    elif (
        verdict is not None
        and environment
        and hmac.compare_digest(verdict.fingerprint, fingerprint(environment))
    ):
        last = (verdict.status, verdict.checkedAt, verdict.error)
    else:
        last = (STATUS_UNKNOWN, None, None)
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


async def _safe_probe(spec: ManagedKey, value: str) -> tuple[bool, str | None]:
    try:
        ok, error = await spec.probe(value)
    except Exception as exc:
        logger.warning("key probe failed", extra={"error": type(exc).__name__})
        return False, "The key couldn't be tested. Try again."
    if error and value and len(value) >= 8:
        error = error.replace(value, "***")
    return ok, error


async def test_secret(session: AsyncSession, key: str) -> dict[str, Any]:
    spec = MANAGED_KEYS[key]
    await refresh_if_stale(session, force=True)
    value = peek_secret(key)
    checked_at = datetime.now(UTC)
    ok, error = (False, "Not configured") if not value else await _safe_probe(spec, value)
    status_text = STATUS_OK if ok else STATUS_FAILED
    row = (await session.execute(select(ManagedSecret).where(ManagedSecret.key == key))).scalar_one_or_none()
    if row is not None and decrypt(row.valueEnc) is not None:
        row.lastStatus = status_text
        row.lastCheckedAt = checked_at
        row.lastError = None if ok else error
    elif value:
        payload = {
            "status": status_text,
            "checkedAt": checked_at,
            "error": None if ok else error,
            "fingerprint": fingerprint(value),
        }
        await session.execute(
            insert(SecretTestResult)
            .values(key=key, **payload)
            .on_conflict_do_update(index_elements=[SecretTestResult.key], set_=payload)
        )
    await session.commit()
    described = await describe_secret(session, key)
    described["lastStatus"] = status_text
    described["lastCheckedAt"] = checked_at.isoformat()
    described["lastError"] = None if ok else error
    return described
