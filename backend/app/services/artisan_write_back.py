from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.composer.candidates import field_evidence_id
from app.models import Answer
from app.research.evidence import Quote, SourceDocument
from app.research.write_back import ClaimWriteBack, WriteBackCitation, WriteBackSubject

from .artisan_turns import UnquotedTurn
from .claim_pages import refresh_claim_pages
from .curation_keys import DISCIPLINE_CONCEPT_TYPES
from .field_voices_citations import field_hit_documents
from .research_write_back import shown_results, write_through_gates
from .write_back_plan import FIELD_ONLY_DISCIPLINES, WRITE_BACK_PREDICATE

__all__ = [
    "ARTISAN_QUOTED_REASON",
    "TurnFiling",
    "WrittenTurn",
    "turn_claim",
    "turn_claim_text",
    "writes_turns_back",
    "written_turns",
]

logger = logging.getLogger(__name__)

ARTISAN_QUOTED_REASON = (
    "Field interview: the artisan's own words, quoted verbatim from a turn the portal marks quotable"
)


@dataclass(frozen=True)
class TurnFiling:
    craft_slug: str
    craft_name: str
    field: str
    answer_id: uuid.UUID


@dataclass(frozen=True)
class WrittenTurn:
    claim_id: uuid.UUID
    unquoted: UnquotedTurn


def writes_turns_back(field: str) -> bool:
    return field in FIELD_ONLY_DISCIPLINES


def turn_claim_text(craft_name: str, quote: str) -> str:
    return f"An artisan who practises {craft_name} says: “{quote}”"


def turn_claim(unquoted: UnquotedTurn, document: SourceDocument, filing: TurnFiling) -> ClaimWriteBack:
    quote = Quote(text=unquoted.quote, locator=unquoted.hit.locator)
    evidence = document.item.model_copy(update={"quotes": [quote]})
    return ClaimWriteBack(
        craft_slug=filing.craft_slug,
        subject=WriteBackSubject(
            concept_type=DISCIPLINE_CONCEPT_TYPES[filing.field], concept_name=filing.craft_name
        ),
        field=filing.field,
        predicate=WRITE_BACK_PREDICATE,
        text=turn_claim_text(filing.craft_name, unquoted.quote),
        label="QUOTED",
        level_reason=ARTISAN_QUOTED_REASON,
        citations=[WriteBackCitation(evidence=evidence, quote=quote, quote_check="PASS", relation="DIRECT")],
        found_by="ANSWER",
        answer_id=filing.answer_id,
    )


async def written_turns(
    session: AsyncSession, filing: TurnFiling, turns: Sequence[UnquotedTurn]
) -> list[WrittenTurn]:
    if not turns or not writes_turns_back(filing.field):
        return []
    if await session.scalar(select(Answer.id).where(Answer.id == filing.answer_id)) is None:
        logger.info("answer %s is not stored, so no artisan turn is written back", filing.answer_id)
        return []
    documents = await field_hit_documents(session, [turn.hit for turn in turns])
    planned = _planned(turns, documents, filing)
    if not planned:
        return []
    claims = [claim for claim, _ in planned.values()]
    written = await write_through_gates(session, claims, documents, embed=None, judge=None)
    await session.commit()
    await refresh_claim_pages(session, shown_results(written.filed, live=written.live))
    return [
        WrittenTurn(result.claim_id, planned[result.dedupe_key][1])
        for result in written.filed
        if result.dedupe_key in planned
    ]


def _planned(
    turns: Sequence[UnquotedTurn], documents: Mapping[str, SourceDocument], filing: TurnFiling
) -> dict[str, tuple[ClaimWriteBack, UnquotedTurn]]:
    planned: dict[str, tuple[ClaimWriteBack, UnquotedTurn]] = {}
    for turn in turns:
        document = documents.get(field_evidence_id(turn.hit))
        if document is None:
            continue
        try:
            claim = turn_claim(turn, document, filing)
        except ValidationError as refused:
            logger.info("an artisan turn of %s is not written back: %s", filing.craft_slug, refused)
            continue
        planned.setdefault(claim.dedupe_key, (claim, turn))
    return planned
