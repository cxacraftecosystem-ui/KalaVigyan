from __future__ import annotations

import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, InvalidInput
from app.models import Answer, SavedItem
from app.research.explainer_versions import (
    EXPLAINER_VERSION_SCHEMA_VERSION,
    BuildsOn,
    ExplainerHistory,
    ExplainerVersionDocument,
    VersionMark,
)

from .explainer_payload import (
    EXPLAINER_PAYLOAD_KEY,
    FIRST_VERSION,
    VERSION_PAYLOAD_KEY,
    first_version_mark,
    stored_mark,
    stored_version,
)
from .field_voices_readback import current_field_voices
from .follow_ups import FollowUp
from .simulation_hiding import with_hidden_marks
from .testimony_readback import current_quotes

__all__ = [
    "STALE_VERSION_DETAIL",
    "UNKNOWN_EXPLAINER_DETAIL",
    "StaleVersion",
    "UnknownExplainer",
    "explainer_history",
    "explainer_version",
    "follow_up_of",
    "latest_stored",
    "latest_version",
    "mark_seen",
    "owned_explainer",
    "shown_version",
]

UNKNOWN_EXPLAINER_DETAIL = "No explainer has that address."
STALE_VERSION_DETAIL = "A newer version of this explainer was saved meanwhile. Open it to ask again."


class UnknownExplainer(AppError):
    def __init__(self, explainer_id: uuid.UUID) -> None:
        super().__init__(f"the reader has no explainer {explainer_id}")
        self.explainer_id = explainer_id


class StaleVersion(AppError):
    def __init__(self, explainer_id: uuid.UUID, asked: int, latest: int) -> None:
        super().__init__(f"explainer {explainer_id} is at version {latest}, not {asked}")
        self.latest = latest


def owned_explainer(explainer_id: uuid.UUID, user_id: uuid.UUID) -> list[ColumnElement[bool]]:
    return [Answer.explainerId == explainer_id, Answer.userId == user_id]


async def explainer_history(
    session: AsyncSession, explainer_id: uuid.UUID, user_id: uuid.UUID
) -> ExplainerHistory:
    document = Answer.payload[EXPLAINER_PAYLOAD_KEY]
    rows = (
        await session.execute(
            select(
                Answer.id,
                Answer.explainerVersion,
                Answer.payload[VERSION_PAYLOAD_KEY],
                document["question"],
                document["createdAt"],
            )
            .where(*owned_explainer(explainer_id, user_id))
            .order_by(Answer.explainerVersion)
        )
    ).all()
    if not rows:
        raise UnknownExplainer(explainer_id)
    try:
        return ExplainerHistory(
            schema_version=EXPLAINER_VERSION_SCHEMA_VERSION,
            explainer_id=explainer_id,
            versions=[_mark(tuple(row)) for row in rows],
        )
    except ValidationError as error:
        raise InvalidInput(f"the stored versions of explainer {explainer_id} break the contract") from error


async def explainer_version(
    session: AsyncSession, explainer_id: uuid.UUID, user_id: uuid.UUID, number: int
) -> ExplainerVersionDocument:
    row = (
        await session.execute(
            select(Answer.id, Answer.payload).where(
                *owned_explainer(explainer_id, user_id), Answer.explainerVersion == number
            )
        )
    ).first()
    if row is None:
        raise UnknownExplainer(explainer_id)
    return await shown_version(session, stored_version(row[0], number, row[1]))


async def latest_version(
    session: AsyncSession, explainer_id: uuid.UUID, user_id: uuid.UUID
) -> ExplainerVersionDocument:
    return await shown_version(session, await latest_stored(session, explainer_id, user_id))


async def follow_up_of(session: AsyncSession, user_id: uuid.UUID, builds_on: BuildsOn) -> FollowUp:
    latest = await latest_stored(session, builds_on.explainer_id, user_id)
    if latest.mark.version != builds_on.version:
        raise StaleVersion(builds_on.explainer_id, builds_on.version, latest.mark.version)
    return FollowUp(base=latest, facets=tuple(builds_on.facets))


async def mark_seen(session: AsyncSession, user_id: uuid.UUID, explainer_id: uuid.UUID, version: int) -> None:
    await session.execute(
        update(SavedItem)
        .where(SavedItem.userId == user_id, SavedItem.answerId == explainer_id)
        .values(seenVersion=func.greatest(SavedItem.seenVersion, version))
    )


async def latest_stored(
    session: AsyncSession, explainer_id: uuid.UUID, user_id: uuid.UUID
) -> ExplainerVersionDocument:
    row = (
        await session.execute(
            select(Answer.id, Answer.explainerVersion, Answer.payload)
            .where(*owned_explainer(explainer_id, user_id))
            .order_by(Answer.explainerVersion.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        raise UnknownExplainer(explainer_id)
    return stored_version(row[0], row[1], row[2])


async def shown_version(
    session: AsyncSession, document: ExplainerVersionDocument
) -> ExplainerVersionDocument:
    shown = await current_quotes(session, await with_hidden_marks(session, document.explainer))
    current = await current_field_voices(session, shown)
    if current is None:
        raise UnknownExplainer(document.explainer.answer_id)
    return document.model_copy(update={"explainer": current})


def _mark(row: tuple[Any, ...]) -> VersionMark:
    answer_id, number, stored, question, created_at = row
    if number == FIRST_VERSION:
        return first_version_mark(answer_id=answer_id, question=question, created_at=created_at)
    return stored_mark(answer_id, number, stored)
