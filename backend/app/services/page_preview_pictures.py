from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.core.roles import Capability, can
from app.models import ImageContribution, MediaAsset, User
from app.research.craft_contributed import CONTRIBUTED_MIMES
from app.research.page_proposals import ACCEPTED, PICTURE, PartReport

from .field_photo_scope import served_photo
from .field_voices_image_store import IMAGE_ROUTE
from .monograph_generated_pictures import PlateSource, plates_of
from .open_work_subjects import CATEGORY, WorkSubject
from .page_preview_links import UnknownPreview, passed_preview

__all__ = [
    "GIVEN_STATUSES",
    "NO_CATEGORY",
    "OwnPicture",
    "checked_given",
    "given_picture_report",
    "given_plates",
    "own_picture_file",
    "pass_field_photo",
    "pass_picture_file",
    "preview_picture_url",
    "shown_picture_file",
]

GIVEN_STATUSES = ("PENDING", "APPROVED")
APPROVED = "APPROVED"
PREVIEW_PICTURE_PATH = "/api/knowledge/pages/pictures/{id}"
NOT_GIVEN = "No picture this account gave to {slug} has the id {id}; give it with give_pictures first, then name it here."
NO_CATEGORY = "A picture is given to a craft's page; a category's bundle carries none."
GIVEN_WAITING = "Given already: the page draws it in its place once an Admin approves it."
GIVEN_SHOWN = "Given already and approved: the page draws it in its place."


@dataclass(frozen=True)
class OwnPicture:
    key: str
    mime: str


def preview_picture_url(contribution_id: uuid.UUID) -> str:
    return PREVIEW_PICTURE_PATH.format(id=contribution_id)


async def checked_given(
    session: AsyncSession, user: User, subject: WorkSubject, ids: Sequence[uuid.UUID]
) -> list[tuple[ImageContribution, MediaAsset]]:
    rows = await _given(session, user, subject, ids)
    missing = [str(given) for given in ids if given not in {row.id for row, _ in rows}]
    if missing:
        raise InvalidInput(NOT_GIVEN.format(slug=subject.slug, id=", ".join(missing)))
    return rows


async def given_plates(
    session: AsyncSession, user: User, subject: WorkSubject, ids: Sequence[uuid.UUID]
) -> list[PlateSource]:
    return await plates_of(session, await checked_given(session, user, subject, ids), preview_picture_url)


async def given_picture_report(
    session: AsyncSession, user: User, subject: WorkSubject, index: int, contribution_id: uuid.UUID
) -> PartReport:
    ((row, _),) = await checked_given(session, user, subject, [contribution_id])
    message = GIVEN_SHOWN if row.status == APPROVED else GIVEN_WAITING
    return PartReport(
        part=PICTURE, index=index, outcome=ACCEPTED, status=row.status, id=str(row.id), message=message
    )


async def own_picture_file(
    session: AsyncSession, user: User, contribution_id: uuid.UUID
) -> OwnPicture | None:
    return await _picture_file(session, contribution_id, _own(user))


async def shown_picture_file(
    session: AsyncSession, user: User, contribution_id: uuid.UUID
) -> OwnPicture | None:
    found = await own_picture_file(session, user, contribution_id)
    if found is not None or not can(user, Capability.REVIEW_CONTRIBUTIONS):
        return found
    return await _picture_file(session, contribution_id, _a_given_file())


async def pass_picture_file(
    session: AsyncSession, render_pass: str, contribution_id: uuid.UUID, *, now: datetime
) -> OwnPicture | None:
    try:
        row = await passed_preview(session, render_pass, now=now)
    except UnknownPreview:
        return None
    if preview_picture_url(contribution_id) not in json.dumps(row.document):
        return None
    owner = await session.get(User, row.userId)
    return None if owner is None else await shown_picture_file(session, owner, contribution_id)


async def pass_field_photo(
    session: AsyncSession, render_pass: str, image_id: uuid.UUID, *, now: datetime
) -> OwnPicture | None:
    try:
        row = await passed_preview(session, render_pass, now=now)
    except UnknownPreview:
        return None
    if IMAGE_ROUTE.format(id=image_id) not in json.dumps(row.document):
        return None
    served = await served_photo(session, image_id)
    return None if served is None else OwnPicture(key=served.key, mime=served.mime)


async def _given(
    session: AsyncSession, user: User, subject: WorkSubject, ids: Sequence[uuid.UUID]
) -> list[tuple[ImageContribution, MediaAsset]]:
    if subject.kind == CATEGORY:
        raise InvalidInput(NO_CATEGORY)
    if not ids:
        return []
    rows = await session.execute(
        select(ImageContribution, MediaAsset)
        .join(MediaAsset, MediaAsset.id == ImageContribution.assetId)
        .where(ImageContribution.id.in_(list(ids)), ImageContribution.craftId == subject.id, _own(user))
        .order_by(ImageContribution.createdAt, ImageContribution.id)
    )
    return [(row, asset) for row, asset in rows.all()]


async def _picture_file(
    session: AsyncSession, contribution_id: uuid.UUID, condition: ColumnElement[bool]
) -> OwnPicture | None:
    found = (
        await session.execute(
            select(MediaAsset.s3Key, MediaAsset.mime)
            .select_from(ImageContribution)
            .join(MediaAsset, MediaAsset.id == ImageContribution.assetId)
            .where(ImageContribution.id == contribution_id, condition)
        )
    ).first()
    return None if found is None else OwnPicture(key=found.s3Key, mime=found.mime)


def _own(user: User) -> ColumnElement[bool]:
    return and_(ImageContribution.contributorId == user.id, _a_given_file())


def _a_given_file() -> ColumnElement[bool]:
    return and_(
        ImageContribution.status.in_(GIVEN_STATUSES),
        ImageContribution.sha256.is_not(None),
        MediaAsset.mime.in_(CONTRIBUTED_MIMES),
        MediaAsset.width.is_not(None),
        MediaAsset.height.is_not(None),
    )
