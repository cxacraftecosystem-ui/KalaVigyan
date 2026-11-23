import asyncio
import base64
import hashlib
import hmac
import re
import secrets
import struct
import time
from urllib.parse import quote, urlencode

import segno

from app.core.security import hash_password, verify_password

__all__ = [
    "DIGITS",
    "PERIOD_SECONDS",
    "RECOVERY",
    "RECOVERY_ALPHABET",
    "RECOVERY_CODE_COUNT",
    "RECOVERY_GROUP",
    "SECRET_BYTES",
    "TOTP",
    "TOTP_ISSUER",
    "WINDOW_STEPS",
    "canonical_recovery_code",
    "code_kind",
    "current_totp",
    "generate_recovery_codes",
    "generate_secret",
    "hash_recovery_codes",
    "hotp",
    "match_totp_step",
    "matching_hash",
    "qr_svg",
    "time_step",
    "totp_uri",
]

DIGITS = 6
PERIOD_SECONDS = 30
WINDOW_STEPS = 1
SECRET_BYTES = 20
TOTP_ISSUER = "KalaVigyan"

RECOVERY_CODE_COUNT = 10
RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
RECOVERY_GROUP = 4

TOTP = "totp"
RECOVERY = "recovery"


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode("ascii").rstrip("=")


def _b32decode(secret: str) -> bytes:
    cleaned = re.sub(r"\s", "", secret).upper().rstrip("=")
    return base64.b32decode(cleaned + "=" * (-len(cleaned) % 8))


def hotp(key: bytes, counter: int) -> str:
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(binary % 10**DIGITS).zfill(DIGITS)


def time_step(at: float | None = None) -> int:
    return int((time.time() if at is None else at) // PERIOD_SECONDS)


def current_totp(secret: str, at: float | None = None) -> str:
    return hotp(_b32decode(secret), time_step(at))


def match_totp_step(secret: str, code: str, at: float | None = None) -> int | None:
    normalised = re.sub(r"\s", "", code or "")
    if not re.fullmatch(r"[0-9]{6}", normalised):
        return None
    try:
        key = _b32decode(secret)
    except ValueError, TypeError:
        return None
    counter = time_step(at)
    matched: int | None = None
    for offset in range(-WINDOW_STEPS, WINDOW_STEPS + 1):
        if hmac.compare_digest(hotp(key, counter + offset), normalised):
            matched = counter + offset
    return matched


def totp_uri(secret: str, account_name: str, issuer: str = TOTP_ISSUER) -> str:
    label = quote(f"{issuer}:{account_name}", safe="")
    params = urlencode(
        {"secret": secret, "issuer": issuer, "algorithm": "SHA1", "digits": DIGITS, "period": PERIOD_SECONDS},
        quote_via=quote,
    )
    return f"otpauth://totp/{label}?{params}"


def qr_svg(text: str) -> str:
    code = segno.make(text, error="m", micro=False, boost_error=False)
    border = 4
    rows = [[bool(cell) for cell in row] for row in code.matrix]
    size = len(rows[0]) + 2 * border
    commands: list[str] = []
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            if not row[x]:
                x += 1
                continue
            start = x
            while x < len(row) and row[x]:
                x += 1
            commands.append(f"M{start + border} {y + border}h{x - start}v1h-{x - start}z")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" shape-rendering="crispEdges">'
        f'<rect width="{size}" height="{size}" fill="#ffffff"/>'
        f'<path fill="#000000" d="{"".join(commands)}"/></svg>'
    )


def generate_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(RECOVERY_GROUP * 2))
        codes.append(f"{raw[:RECOVERY_GROUP]}-{raw[RECOVERY_GROUP:]}")
    return codes


def canonical_recovery_code(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]", "", (text or "").lower())
    if len(cleaned) == RECOVERY_GROUP * 2:
        return f"{cleaned[:RECOVERY_GROUP]}-{cleaned[RECOVERY_GROUP:]}"
    return cleaned


def code_kind(text: str) -> str | None:
    compact = re.sub(r"[\s-]", "", text or "")
    if re.fullmatch(r"[0-9]{6}", compact):
        return TOTP
    if re.fullmatch(r"[A-Za-z0-9]{8}", compact):
        return RECOVERY
    return None


async def hash_recovery_codes(codes: list[str]) -> list[str]:
    return list(
        await asyncio.gather(*(asyncio.to_thread(hash_password, canonical_recovery_code(c)) for c in codes))
    )


async def matching_hash(stored: list[str], submitted: str) -> str | None:
    canonical = canonical_recovery_code(submitted)
    verdicts = await asyncio.gather(*(asyncio.to_thread(verify_password, canonical, h) for h in stored))
    match = None
    for hashed, ok in zip(stored, verdicts, strict=True):
        if ok:
            match = hashed
    return match
