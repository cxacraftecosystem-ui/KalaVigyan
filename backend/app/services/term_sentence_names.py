from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, Term, TermConcept
from app.research.sentence_names import sentence_name

__all__ = ["CONCEPT_SUBJECT", "fill_sentence_names", "named_in_sentences"]

CONCEPT_SUBJECT = "CONCEPT"


async def fill_sentence_names(session: AsyncSession) -> int:
    rows = await session.execute(
        select(Term.id, Term.label, Term.meaning, Claim.text)
        .join(TermConcept, TermConcept.termId == Term.id)
        .join(Claim, and_(Claim.subjectType == CONCEPT_SUBJECT, Claim.subjectId == TermConcept.conceptId))
        .where(Term.sentenceName.is_(None))
        .order_by(Term.id, Claim.id)
    )
    named = named_in_sentences(rows.tuples().all())
    for term_id, name in named.items():
        await session.execute(update(Term).where(Term.id == term_id).values(sentenceName=name))
    return len(named)


def named_in_sentences(rows: Iterable[tuple[uuid.UUID, str, str | None, str]]) -> dict[uuid.UUID, str]:
    labels: dict[uuid.UUID, str] = {}
    texts: dict[uuid.UUID, list[str]] = {}
    for term_id, label, meaning, text in rows:
        labels[term_id] = label
        texts.setdefault(term_id, [meaning] if meaning else []).append(text)
    found = {term_id: sentence_name(labels[term_id], texts[term_id]) for term_id in labels}
    return {term_id: name for term_id, name in found.items() if name is not None}
