from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from collections.abc import Sequence
from contextlib import suppress
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.key_catalogue import MANAGED_KEYS
from app.models import ManagedSecret

__all__ = [
    "CACHE_TTL_SECONDS",
    "STATUS_FAILED",
    "STATUS_OK",
    "STATUS_UNKNOWN",
    "KeyCache",
    "decrypt",
    "encrypt",
    "env_value",
    "fingerprint",
    "get_secret",
    "invalidate",
    "keys",
    "peek_secret",
    "refresh_if_stale",
]

logger = logging.getLogger(__name__)

_HKDF_INFO = b"kalavigyan/managed-secrets/v1"
_FINGERPRINT_HKDF_INFO = b"kalavigyan/secret-verdict-fingerprint/v1"
CACHE_TTL_SECONDS = 30.0

STATUS_UNKNOWN = "UNKNOWN"
STATUS_OK = "OK"
STATUS_FAILED = "FAILED"


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


def env_value(key: str) -> str | None:
    spec = MANAGED_KEYS.get(key)
    if spec is None:
        return None
    value = getattr(get_settings(), spec.settings_attr, None)
    text = str(value).strip() if value is not None else ""
    return text or None


class KeyCache:
    def __init__(self, *, ttl_seconds: float = CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._overrides: dict[str, str] = {}
        self._loaded_at = 0.0

    def invalidate(self) -> None:
        self._loaded_at = 0.0

    def fresh(self) -> bool:
        return self._loaded_at > 0.0 and (time.monotonic() - self._loaded_at) < self._ttl

    async def refresh_if_stale(self, session: AsyncSession, *, force: bool = False) -> None:
        if not force and self.fresh():
            return
        try:
            rows = (await session.execute(select(ManagedSecret))).scalars().all()
        except Exception as error:
            logger.warning(
                "could not load managed secrets; using environment values",
                extra={"error": type(error).__name__},
            )
            return
        self._overrides = _readable(rows)
        self._loaded_at = time.monotonic()

    def peek(self, key: str) -> str | None:
        return self._overrides.get(key) or env_value(key)


def _readable(rows: Sequence[ManagedSecret]) -> dict[str, str]:
    fresh: dict[str, str] = {}
    for row in rows:
        if row.key not in MANAGED_KEYS:
            continue
        plaintext = decrypt(row.valueEnc)
        if plaintext is None:
            logger.error("managed secret could not be decrypted", extra={"key": row.key})
            continue
        fresh[row.key] = plaintext
    return fresh


keys = KeyCache()


def invalidate() -> None:
    keys.invalidate()


async def refresh_if_stale(session: AsyncSession, force: bool = False) -> None:
    await keys.refresh_if_stale(session, force=force)


def peek_secret(key: str) -> str | None:
    return keys.peek(key)


async def get_secret(session: AsyncSession, key: str) -> str | None:
    await refresh_if_stale(session)
    return peek_secret(key)
