from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import ImageContribution, MediaAsset, User
from app.research.craft_contributed import CONTRIBUTED_MIMES
from app.research.page_proposals import ACCEPTED, PICTURE, PartReport

from .monograph_generated_pictures import PlateSource, plates_of
from .open_work_subjects import CATEGORY, WorkSubject

__all__ = [
    "GIVEN_STATUSES",
    "OwnPicture",
    "given_picture_report",
    "given_plates",
    "own_picture_file",
    "preview_picture_url",
]

GIVEN_STATUSES = ("PENDING", "APPROVED")
APPROVED = "APPROVED"
PREVIEW_PICTURE_PATH = "/api/knowledge/pages/pictures/{id}"
NOT_GIVEN = "No picture this account gave to {slug} has the id {id}; give it with give_image first, then name it here."
NO_CATEGORY = "A picture is given to a craft's page; a category's bundle carries none."
GIVEN_WAITING = "Given already: the page draws it in its place once an Admin approves it."
GIVEN_SHOWN = "Given already and approved: the page draws it in its place."


@dataclass(frozen=True)
class OwnPicture:
    key: str
    mime: str


def preview_picture_url(contribution_id: uuid.UUID) -> str:
    return PREVIEW_PICTURE_PATH.format(id=contribution_id)


async def given_plates(
    session: AsyncSession, user: User, subject: WorkSubject, ids: Sequence[uuid.UUID]
) -> list[PlateSource]:
    rows = await _given(session, user, subject, ids)
    missing = [str(given) for given in ids if given not in {row.id for row, _ in rows}]
    if missing:
        raise InvalidInput(NOT_GIVEN.format(slug=subject.slug, id=", ".join(missing)))
    return await plates_of(session, rows, preview_picture_url)


async def given_picture_report(
    session: AsyncSession, user: User, subject: WorkSubject, index: int, contribution_id: uuid.UUID
) -> PartReport:
    rows = await _given(session, user, subject, [contribution_id])
    if not rows:
        raise InvalidInput(NOT_GIVEN.format(slug=subject.slug, id=contribution_id))
    ((row, _),) = rows
    message = GIVEN_SHOWN if row.status == APPROVED else GIVEN_WAITING
    return PartReport(
        part=PICTURE, index=index, outcome=ACCEPTED, status=row.status, id=str(row.id), message=message
    )


async def own_picture_file(
    session: AsyncSession, user: User, contribution_id: uuid.UUID
) -> OwnPicture | None:
    found = (
        await session.execute(
            select(MediaAsset.s3Key, MediaAsset.mime)
            .select_from(ImageContribution)
            .join(MediaAsset, MediaAsset.id == ImageContribution.assetId)
            .where(ImageContribution.id == contribution_id, _own(user))
        )
    ).first()
    return None if found is None else OwnPicture(key=found.s3Key, mime=found.mime)


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


def _own(user: User) -> ColumnElement[bool]:
    return and_(
        ImageContribution.contributorId == user.id,
        ImageContribution.status.in_(GIVEN_STATUSES),
        ImageContribution.sha256.is_not(None),
        MediaAsset.mime.in_(CONTRIBUTED_MIMES),
        MediaAsset.width.is_not(None),
        MediaAsset.height.is_not(None),
    )
