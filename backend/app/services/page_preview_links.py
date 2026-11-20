from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import secret_key
from app.models import PagePreview, User
from app.research.monograph_document import MonographDocument

__all__ = [
    "LIVE_PREVIEWS_MAX",
    "PREVIEW_LIFETIME",
    "UnknownPreview",
    "preview_document",
    "preview_key",
    "preview_path",
    "signed_token",
    "store_preview",
    "token_preview",
]

PREVIEW_LIFETIME = timedelta(hours=24)
LIVE_PREVIEWS_MAX = 20
PREVIEW_PATH = "/preview/{token}"
KEY_CONTEXT = b"kalavigyan page preview"
TOKEN = re.compile(r"^([0-9a-f]{32})\.(\d{1,12})\.([0-9a-f]{64})$")
UNKNOWN = "No preview of yours has this link, or it has expired: call preview_page again."


class UnknownPreview(Exception):
    pass


def preview_key() -> bytes:
    secret = secret_key("JWT_SECRET", get_settings().jwt_secret)
    return hmac.new(secret, KEY_CONTEXT, hashlib.sha256).digest()


def preview_path(token: str) -> str:
    return PREVIEW_PATH.format(token=token)


def signed_token(preview_id: uuid.UUID, user_id: uuid.UUID, expires_at: datetime, key: bytes) -> str:
    body = f"{preview_id.hex}.{int(expires_at.timestamp())}"
    return f"{body}.{_mac(body, user_id, key)}"


def token_preview(token: str, user_id: uuid.UUID, key: bytes, *, now: datetime) -> uuid.UUID:
    found = TOKEN.match(token)
    if found is None:
        raise UnknownPreview(UNKNOWN)
    preview_hex, stamp, mac = found.groups()
    if not hmac.compare_digest(mac, _mac(f"{preview_hex}.{stamp}", user_id, key)):
        raise UnknownPreview(UNKNOWN)
    if int(stamp) <= now.timestamp():
        raise UnknownPreview(UNKNOWN)
    return uuid.UUID(hex=preview_hex)


async def store_preview(
    session: AsyncSession, user: User, document: MonographDocument, *, now: datetime
) -> tuple[PagePreview, str]:
    await _prune(session, user.id, now)
    row = PagePreview(
        id=uuid.uuid4(),
        userId=user.id,
        subjectKind=document.subject_kind,
        subjectSlug=document.subject_slug,
        document=document.model_dump(mode="json", by_alias=True),
        expiresAt=now + PREVIEW_LIFETIME,
        createdAt=now,
    )
    session.add(row)
    await session.flush()
    return row, signed_token(row.id, user.id, row.expiresAt, preview_key())


async def preview_document(session: AsyncSession, user: User, token: str, *, now: datetime) -> dict[str, Any]:
    preview_id = token_preview(token, user.id, preview_key(), now=now)
    row = await session.get(PagePreview, preview_id)
    if row is None or row.userId != user.id or row.expiresAt <= now:
        raise UnknownPreview(UNKNOWN)
    return row.document


async def _prune(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> None:
    await session.execute(
        delete(PagePreview).where(PagePreview.userId == user_id, PagePreview.expiresAt <= now)
    )
    live = list(
        await session.scalars(
            select(PagePreview.id).where(PagePreview.userId == user_id).order_by(PagePreview.createdAt.desc())
        )
    )
    stale = live[LIVE_PREVIEWS_MAX - 1 :]
    if stale:
        await session.execute(delete(PagePreview).where(PagePreview.id.in_(stale)))


def _mac(body: str, user_id: uuid.UUID, key: bytes) -> str:
    return hmac.new(key, f"{body}.{user_id.hex}".encode(), hashlib.sha256).hexdigest()
