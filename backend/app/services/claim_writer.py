from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.data.craft_master_loader import ID_NAMESPACE
from app.models import Claim, ClaimSource, Concept, Craft, Process, ProcessStage, ReviewEvent
from app.research.quotes import quote_key
from app.research.write_back import (
    WRITE_BACK_ORIGIN,
    WRITE_BACK_STATUS,
    ClaimWriteBack,
    WriteBackCitation,
    WriteBackResult,
    WriteBackSubject,
)

from .live_source_store import chunk_for_quote, source_for

__all__ = [
    "LIVE_CONCEPT_ORIGIN",
    "SHARED_CONCEPT_KEYS",
    "WRITE_BACK_ACTOR",
    "CraftKeys",
    "SqlClaimWriter",
    "citation_id",
    "concept_id_for",
    "craft_keys",
    "write_back_claim_id",
]

WRITE_BACK_ACTOR = "live_research"
LIVE_CONCEPT_ORIGIN = "live_research"
STAGE_CONCEPT_TYPE = "PROCESS_STAGE"
RAISABLE_LEVEL = "HYPOTHESIS"
QUOTED_LEVEL = "PROVISIONAL"
CLOSED_STATUSES = ("REJECTED", "RETRACTED")
SHARED_OWNER = "shared"


@dataclass(frozen=True)
class CraftKeys:
    craft_id: uuid.UUID | None
    sub_category_id: uuid.UUID | None


SHARED_CONCEPT_KEYS = CraftKeys(craft_id=None, sub_category_id=None)


def write_back_claim_id(dedupe_key: str) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"claim-write-back:{dedupe_key}")


def citation_id(claim_id: uuid.UUID, source_key: str, quote: str | None) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"claim-source:{claim_id}:{source_key}:{quote_key(quote or '')}")


class SqlClaimWriter:
    def __init__(self, session: AsyncSession, *, status: str = WRITE_BACK_STATUS) -> None:
        self._session = session
        self._status = status

    async def write(self, claims: Sequence[ClaimWriteBack]) -> list[WriteBackResult]:
        results = [await self._write_one(claim) for claim in claims]
        await self._session.flush()
        return results

    async def _write_one(self, claim: ClaimWriteBack) -> WriteBackResult:
        craft = await craft_keys(self._session, claim.craft_slug)
        concept_id = await concept_id_for(self._session, craft, claim.subject)
        claim_id = write_back_claim_id(claim.dedupe_key)
        created = await self._insert_claim(claim_id, concept_id, claim)
        if not created:
            await self._raise_level(claim_id, claim)
        for citation in claim.citations:
            await self._cite(claim_id, citation, claim)
        return WriteBackResult(dedupe_key=claim.dedupe_key, claim_id=claim_id, created=created)

    async def _insert_claim(self, claim_id: uuid.UUID, concept_id: uuid.UUID, claim: ClaimWriteBack) -> bool:
        inserted = await self._session.scalar(
            insert(Claim)
            .values(
                id=claim_id,
                subjectType="CONCEPT",
                subjectId=concept_id,
                predicate=claim.predicate,
                text=claim.text,
                textLang=claim.text_lang,
                valueNum=claim.value_num,
                valueUnit=claim.value_unit,
                evidenceLevel=claim.evidence_level,
                levelReason=claim.level_reason,
                origin=WRITE_BACK_ORIGIN,
                status=self._status,
                createdByKind="SYSTEM",
                field=claim.stored_field,
            )
            .on_conflict_do_nothing()
            .returning(Claim.id)
        )
        if inserted is None:
            return False
        self._session.add(_event(claim_id, claim, from_level=None, to_status=self._status))
        return True

    async def _raise_level(self, claim_id: uuid.UUID, claim: ClaimWriteBack) -> None:
        if claim.evidence_level != QUOTED_LEVEL:
            return
        raised = await self._session.scalar(
            update(Claim)
            .where(
                Claim.id == claim_id,
                Claim.evidenceLevel == RAISABLE_LEVEL,
                Claim.status.not_in(CLOSED_STATUSES),
            )
            .values(evidenceLevel=QUOTED_LEVEL, levelReason=claim.level_reason)
            .returning(Claim.id)
        )
        if raised is not None:
            self._session.add(_event(claim_id, claim, from_level=RAISABLE_LEVEL, to_status=None))

    async def _cite(self, claim_id: uuid.UUID, citation: WriteBackCitation, claim: ClaimWriteBack) -> None:
        item = citation.evidence
        source = await source_for(self._session, item)
        quote = citation.quote
        chunk = await chunk_for_quote(self._session, source.id, quote.text) if quote else None
        await self._session.execute(
            insert(ClaimSource)
            .values(
                id=citation_id(claim_id, item.source_key, quote.text if quote else None),
                claimId=claim_id,
                sourceId=source.id,
                chunkId=chunk.chunk_id if chunk else None,
                locator=(quote.locator if quote else None) or (chunk.locator if chunk else None),
                quote=quote.text if quote else None,
                quoteCheck=citation.quote_check,
                checkedAt=item.retrieved_at if quote else None,
                relation=citation.relation,
                foundBy=claim.found_by,
                answerId=claim.answer_id,
                retrievedAt=item.retrieved_at,
            )
            .on_conflict_do_nothing()
        )


async def concept_id_for(session: AsyncSession, craft: CraftKeys, subject: WriteBackSubject) -> uuid.UUID:
    if subject.concept_id is not None:
        return await _given_concept(session, craft, subject)
    found = await _named_concept(session, craft, subject)
    if found is not None:
        return found
    concept_id = uuid.uuid5(
        ID_NAMESPACE,
        f"live-concept:{craft.craft_id or SHARED_OWNER}:{subject.concept_type}:{_folded(subject.concept_name)}",
    )
    await session.execute(
        insert(Concept)
        .values(
            id=concept_id,
            craftId=craft.craft_id,
            type=subject.concept_type,
            name=subject.concept_name,
            originRef=LIVE_CONCEPT_ORIGIN,
        )
        .on_conflict_do_nothing()
    )
    return concept_id


async def craft_keys(session: AsyncSession, slug: str | None) -> CraftKeys:
    if slug is None:
        return SHARED_CONCEPT_KEYS
    row = (await session.execute(select(Craft.id, Craft.subCategoryId).where(Craft.slug == slug))).first()
    if row is None:
        raise InvalidInput(f"No craft has the slug {slug!r}")
    return CraftKeys(craft_id=row.id, sub_category_id=row.subCategoryId)


async def _given_concept(session: AsyncSession, craft: CraftKeys, subject: WriteBackSubject) -> uuid.UUID:
    concept = await session.get(Concept, subject.concept_id)
    owned = concept is not None and _owns(craft, concept)
    if not owned or concept.type != subject.concept_type:
        raise InvalidInput(f"The concept {subject.concept_id} is not a {subject.concept_type} of this craft")
    return concept.id


async def _named_concept(
    session: AsyncSession, craft: CraftKeys, subject: WriteBackSubject
) -> uuid.UUID | None:
    name = _folded(subject.concept_name)
    if subject.concept_type == STAGE_CONCEPT_TYPE and craft.craft_id is not None:
        stage = await session.scalar(
            select(ProcessStage.conceptId)
            .join(Process, Process.id == ProcessStage.processId)
            .where(
                Process.craftId == craft.craft_id,
                ProcessStage.conceptId.is_not(None),
                func.lower(ProcessStage.name) == name,
            )
            .order_by(Process.id, ProcessStage.ordinal)
            .limit(1)
        )
        if stage is not None:
            return stage
    for owner in _owner_conditions(craft):
        found = await session.scalar(
            select(Concept.id)
            .where(owner, Concept.type == subject.concept_type, func.lower(Concept.name) == name)
            .order_by(Concept.createdAt, Concept.id)
            .limit(1)
        )
        if found is not None:
            return found
    return None


def _event(
    claim_id: uuid.UUID, claim: ClaimWriteBack, *, from_level: str | None, to_status: str | None
) -> ReviewEvent:
    return ReviewEvent(
        claimId=claim_id,
        actorKind="SYSTEM",
        systemActor=WRITE_BACK_ACTOR,
        toStatus=to_status,
        fromLevel=from_level,
        toLevel=claim.evidence_level,
        note=_note(claim),
    )


def _note(claim: ClaimWriteBack) -> str:
    if claim.answer_id is None:
        return f"{claim.found_by} write-back"
    return f"{claim.found_by} write-back, answer {claim.answer_id}"


def _folded(name: str) -> str:
    return " ".join(name.split()).lower()


def _owns(craft: CraftKeys, concept: Concept) -> bool:
    if craft.craft_id is None:
        return concept.craftId is None and concept.subCategoryId is None
    if concept.craftId == craft.craft_id:
        return True
    return craft.sub_category_id is not None and concept.subCategoryId == craft.sub_category_id


def _owner_conditions(craft: CraftKeys) -> list[ColumnElement[bool]]:
    if craft.craft_id is None:
        return [and_(Concept.craftId.is_(None), Concept.subCategoryId.is_(None))]
    owners = [Concept.craftId == craft.craft_id]
    if craft.sub_category_id is not None:
        owners.append(Concept.subCategoryId == craft.sub_category_id)
    return owners
