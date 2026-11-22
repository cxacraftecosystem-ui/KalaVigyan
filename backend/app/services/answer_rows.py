from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models import AnswerCitation, AnswerSentence, AnswerTrace, Claim, ClaimSource, Source
from app.models.enums import EVIDENCE_LEVELS
from app.research.citations import AnswerSentence as ShownAnswerSentence, Citation, SourceRef
from app.research.explainer import Explainer

from .answer_steps import TracedStep

__all__ = ["LEDE_ORDINAL", "OPEN_QUESTIONS_KIND", "ShownSentence", "shown_sentences", "write_answer_rows"]

logger = logging.getLogger(__name__)

LEDE_ORDINAL = 0
OPEN_QUESTIONS_KIND = "open_questions"
TEXT_COLUMN_CHARS = 300
STEP_CHARS = 60


@dataclass(frozen=True)
class ShownSentence:
    section_ordinal: int
    heading: str | None
    ordinal: int
    sentence: ShownAnswerSentence
    open_question: bool = False


def shown_sentences(explainer: Explainer) -> list[ShownSentence]:
    shown: list[ShownSentence] = []
    if explainer.lede is not None:
        shown += _numbered(LEDE_ORDINAL, None, ((s, False) for s in explainer.lede.shown_sentences()))
    for section in explainer.sections:
        found = (
            (s, block.kind == OPEN_QUESTIONS_KIND)
            for block in section.blocks
            for s in block.shown_sentences()
        )
        shown += _numbered(section.order, section.title, found)
    return shown


async def write_answer_rows(
    session: AsyncSession, answer_id: uuid.UUID, explainer: Explainer | None, steps: Sequence[TracedStep]
) -> None:
    session.add_all(
        AnswerTrace(
            answerId=answer_id, step=step.step[:STEP_CHARS], ordinal=n, ms=step.ms, detail=dict(step.detail)
        )
        for n, step in enumerate(steps)
    )
    if explainer is None:
        return
    sentences = shown_sentences(explainer)
    known = await _Known.of(session, [citation for row in sentences for citation in row.sentence.citations])
    sources = {source.id: source for source in explainer.sources}
    stored = [(_sentence_row(answer_id, row), row) for row in sentences]
    session.add_all(sentence for sentence, _ in stored)
    await session.flush()
    session.add_all(
        _citation_row(sentence.id, n, citation, known, sources.get(citation.source_id))
        for sentence, row in stored
        for n, citation in enumerate(row.sentence.citations)
    )


def _numbered(
    section_ordinal: int, heading: str | None, found: Iterable[tuple[ShownAnswerSentence, bool]]
) -> Iterator[ShownSentence]:
    ordinal = 0
    for sentence, open_question in found:
        if sentence.level not in EVIDENCE_LEVELS:
            logger.info("a sentence shown at level %s is not kept as an answer row", sentence.level)
            continue
        ordinal += 1
        title = heading[:TEXT_COLUMN_CHARS] if heading else None
        yield ShownSentence(section_ordinal, title, ordinal, sentence, open_question)


def _sentence_row(answer_id: uuid.UUID, row: ShownSentence) -> AnswerSentence:
    return AnswerSentence(
        id=uuid.uuid4(),
        answerId=answer_id,
        sectionOrdinal=row.section_ordinal,
        sectionHeading=row.heading,
        ordinal=row.ordinal,
        text=row.sentence.text,
        evidenceLevel=row.sentence.level,
        translated=row.sentence.translated,
        openQuestion=row.open_question,
    )


def _citation_row(
    sentence_id: uuid.UUID, ordinal: int, citation: Citation, known: _Known, source: SourceRef | None
) -> AnswerCitation:
    return AnswerCitation(
        sentenceId=sentence_id,
        claimId=known.claim(citation.claim_id),
        claimSourceId=known.claim_source(citation.id),
        sourceId=known.source(citation.source_id),
        quote=citation.quote,
        locator=citation.locator[:TEXT_COLUMN_CHARS] if citation.locator else None,
        url=source.url if source else None,
        sourceLabel=source.title[:TEXT_COLUMN_CHARS] if source else None,
        ordinal=ordinal,
    )


@dataclass(frozen=True)
class _Known:
    claims: frozenset[uuid.UUID]
    claim_sources: frozenset[uuid.UUID]
    sources: frozenset[uuid.UUID]

    @classmethod
    async def of(cls, session: AsyncSession, citations: Sequence[Citation]) -> _Known:
        return cls(
            claims=await _existing(session, Claim.id, (c.claim_id for c in citations)),
            claim_sources=await _existing(session, ClaimSource.id, (c.id for c in citations)),
            sources=await _existing(session, Source.id, (c.source_id for c in citations)),
        )

    def claim(self, text: str) -> uuid.UUID | None:
        return _kept(text, self.claims)

    def claim_source(self, text: str) -> uuid.UUID | None:
        return _kept(text, self.claim_sources)

    def source(self, text: str) -> uuid.UUID | None:
        return _kept(text, self.sources)


async def _existing(
    session: AsyncSession, column: InstrumentedAttribute[uuid.UUID], texts: Iterable[str]
) -> frozenset[uuid.UUID]:
    ids = {found for text in texts if (found := _uuid(text)) is not None}
    if not ids:
        return frozenset()
    return frozenset(await session.scalars(select(column).where(column.in_(ids))))


def _kept(text: str, known: frozenset[uuid.UUID]) -> uuid.UUID | None:
    found = _uuid(text)
    return found if found in known else None


def _uuid(text: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(text)
    except ValueError:
        return None
