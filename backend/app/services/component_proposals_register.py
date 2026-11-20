from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClaimSource, ComponentProposal, KnowledgePiece, KnowledgePieceSubject
from app.research.component_proposals import SUBJECT_LINK
from app.research.component_specs_general_delivery import DELIVERED_KEY

from . import knowledge_view
from .open_work_components import registered_pieces
from .review_queue_errors import DecisionConflict

__all__ = ["TOPIC_PREFIX", "register_component", "registers"]

TOPIC_PREFIX = "component:"
TOPIC_KEY_MAX = 200
LANGUAGE = "en"
DEPTH = "EXPERT"
SUBJECT_COLUMNS = {"CRAFT": "craftId", "CONCEPT": "conceptId", "COMPOUND": "compoundId", "PLACE": "placeKey"}
NOT_SHOWN = "The component rests on facts not shown on any page yet ({ids}): decide those facts first."
NO_SOURCE = "The component's facts cite no source a reader can open, so it cannot be registered."
TAKEN = "A component registered as {label} meanwhile; reload the queue."
GONE = "The component {label} this proposal links is no longer in the library; reject the proposal."


def registers(row: ComponentProposal) -> bool:
    return row.spec is not None or row.extension == SUBJECT_LINK


async def register_component(session: AsyncSession, row: ComponentProposal) -> uuid.UUID:
    if row.extension == SUBJECT_LINK:
        return await _linked(session, row)
    claim_ids = list(row.claimIds)
    visible, _ = await knowledge_view.claims_by_id(session, claim_ids)
    waiting = [str(claim) for claim in claim_ids if claim not in visible]
    if waiting:
        raise DecisionConflict(NOT_SHOWN.format(ids=", ".join(waiting)))
    source_ids = await _source_ids(session, claim_ids)
    if not source_ids:
        raise DecisionConflict(NO_SOURCE)
    piece = KnowledgePiece(**_piece_values(row, claim_ids, source_ids))
    try:
        async with session.begin_nested():
            session.add(piece)
    except IntegrityError as taken:
        raise DecisionConflict(TAKEN.format(label=row.label)) from taken
    await _write_subjects(session, piece.id, row.subjects)
    return piece.id


async def _linked(session: AsyncSession, row: ComponentProposal) -> uuid.UUID:
    piece_id = await session.scalar(
        select(KnowledgePiece.id).where(KnowledgePiece.label == row.label, *registered_pieces())
    )
    if piece_id is None:
        raise DecisionConflict(GONE.format(label=row.label))
    await _write_subjects(session, piece_id, row.subjects)
    return piece_id


async def _source_ids(session: AsyncSession, claim_ids: Sequence[uuid.UUID]) -> list[str]:
    rows = await session.scalars(
        select(ClaimSource.sourceId).where(ClaimSource.claimId.in_(list(claim_ids))).distinct()
    )
    return sorted(str(source_id) for source_id in rows)


def _piece_values(
    row: ComponentProposal, claim_ids: list[uuid.UUID], source_ids: list[str]
) -> dict[str, Any]:
    payload = {DELIVERED_KEY: {"spec": row.spec, "units": row.units}, "proposalId": str(row.id)}
    described = {
        "label": row.label,
        "kind": row.kind,
        "title": row.title,
        "description": row.description,
        "fields": list(row.fields),
        "payload": payload,
        "claimIds": [str(claim) for claim in claim_ids],
    }
    return {
        "craftId": row.craftId,
        "kind": row.kind,
        "facet": row.field,
        "topicKey": f"{TOPIC_PREFIX}{row.label}"[:TOPIC_KEY_MAX],
        "language": LANGUAGE,
        "depth": DEPTH,
        "payload": payload,
        "claimIds": claim_ids,
        "sourceIds": source_ids,
        "contentHash": hashlib.sha256(json.dumps(described, sort_keys=True).encode("utf-8")).hexdigest(),
        "label": row.label,
        "title": row.title,
        "description": row.description,
        "fields": [field for field in row.fields if field != row.field],
    }


async def _write_subjects(
    session: AsyncSession, piece_id: uuid.UUID, subjects: Sequence[dict[str, Any]]
) -> None:
    held = {
        (subject.kind, str(subject.craftId or subject.conceptId or subject.compoundId or subject.placeKey))
        for subject in await session.scalars(
            select(KnowledgePieceSubject).where(KnowledgePieceSubject.pieceId == piece_id)
        )
    }
    for subject in subjects:
        values = await _subject_values(session, subject)
        key = (values["kind"], str(values[SUBJECT_COLUMNS[values["kind"]]]))
        if key in held:
            continue
        held.add(key)
        session.add(KnowledgePieceSubject(pieceId=piece_id, **values))
    await session.flush()


async def _subject_values(session: AsyncSession, subject: dict[str, Any]) -> dict[str, Any]:
    kind, key = str(subject["kind"]), str(subject["key"])
    column = SUBJECT_COLUMNS[kind]
    if kind == "CRAFT":
        craft = await knowledge_view.resolve_craft(session, key)
        if craft is None:
            raise DecisionConflict(f"The craft {key} the component is keyed to no longer exists.")
        return {"kind": kind, column: craft.id}
    if kind == "PLACE":
        return {"kind": kind, column: key}
    return {"kind": kind, column: uuid.UUID(key)}
