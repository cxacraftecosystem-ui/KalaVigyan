import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

__all__ = [
    "KEY_BYTES",
    "LEGACY_PREFIX",
    "VERSIONED_PREFIX",
    "KeyConfigurationError",
    "Keyring",
    "decrypt_secret",
    "encrypt_secret",
    "key_id",
    "keyring",
    "parse_key",
    "verify_key_configuration",
]

_KEY_ID_CONTEXT = b"kalavigyan-totp-key-id-v2"
_LEGACY_CONTEXT = b"kalavigyan-totp-v1"

LEGACY_PREFIX = "v1"
VERSIONED_PREFIX = "v2:"
KEY_BYTES = 32


class KeyConfigurationError(ValueError):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def parse_key(text: str, *, name: str = "TWO_FACTOR_ENCRYPTION_KEY") -> bytes:
    cleaned = re.sub(r"\s", "", text or "")
    try:
        raw = base64.b64decode(
            cleaned.replace("-", "+").replace("_", "/") + "=" * (-len(cleaned) % 4), validate=True
        )
    except ValueError as exc:
        raise KeyConfigurationError(f"{name} is not base64") from exc
    if len(raw) != KEY_BYTES:
        raise KeyConfigurationError(f"{name} must be {KEY_BYTES} random bytes, base64-encoded")
    return raw


def key_id(key: bytes) -> str:
    return _b64(hmac.new(key, _KEY_ID_CONTEXT, hashlib.sha256).digest()[:6])


@dataclass(frozen=True)
class Keyring:
    current: tuple[str, bytes] | None
    readable: dict[str, bytes]


@lru_cache(maxsize=8)
def _keyring(current: str | None, previous: str | None) -> Keyring:
    readable: dict[str, bytes] = {}
    head: tuple[str, bytes] | None = None
    if current and current.strip():
        key = parse_key(current)
        head = (key_id(key), key)
        readable[head[0]] = key
    for index, text in enumerate(part for part in (previous or "").split(",") if part.strip()):
        key = parse_key(text, name=f"TWO_FACTOR_PREVIOUS_KEYS[{index}]")
        readable.setdefault(key_id(key), key)
    return Keyring(current=head, readable=readable)


def keyring() -> Keyring:
    settings = get_settings()
    return _keyring(settings.two_factor_encryption_key, settings.two_factor_previous_keys)


@lru_cache(maxsize=4)
def _legacy_key(jwt_secret: str) -> bytes:
    return hashlib.scrypt(jwt_secret.encode("utf-8"), salt=_LEGACY_CONTEXT, n=2**14, r=8, p=1, dklen=32)


def _seal(key: bytes, plain: str, aad: bytes | None) -> tuple[str, str, str]:
    iv = secrets.token_bytes(12)
    sealed = AESGCM(key).encrypt(iv, plain.encode("utf-8"), aad)
    return _b64(iv), _b64(sealed[-16:]), _b64(sealed[:-16])


def encrypt_secret(plain: str) -> str:
    ring = keyring()
    if ring.current is None:
        return ".".join((LEGACY_PREFIX, *_seal(_legacy_key(get_settings().jwt_secret), plain, None)))
    kid, key = ring.current
    label = f"{VERSIONED_PREFIX}{kid}"
    return ".".join((label, *_seal(key, plain, label.encode("ascii"))))


def decrypt_secret(stored: str | None) -> str | None:
    if not stored:
        return None
    parts = stored.split(".")
    if len(parts) != 4:
        return None
    label = parts[0]
    aad: bytes | None
    if label == LEGACY_PREFIX:
        key, aad = _legacy_key(get_settings().jwt_secret), None
    elif label.startswith(VERSIONED_PREFIX):
        found = keyring().readable.get(label[len(VERSIONED_PREFIX) :])
        if found is None:
            return None
        key, aad = found, label.encode("ascii")
    else:
        return None
    try:
        iv, tag, ciphertext = _unb64(parts[1]), _unb64(parts[2]), _unb64(parts[3])
        return AESGCM(key).decrypt(iv, ciphertext + tag, aad).decode("utf-8")
    except InvalidTag, ValueError:
        return None


def verify_key_configuration() -> None:
    settings = get_settings()
    try:
        keyring()
    except KeyConfigurationError as exc:
        raise RuntimeError(str(exc)) from exc
    if settings.is_production and not (settings.two_factor_encryption_key or "").strip():
        raise RuntimeError("TWO_FACTOR_ENCRYPTION_KEY must be set in production")
