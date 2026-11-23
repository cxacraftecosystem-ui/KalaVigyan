from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from itertools import batched

from sqlalchemy import ColumnElement, and_, case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, Concept, Craft
from app.research.retrieval import OPEN_CHUNK_ACLS, VISIBLE_SENSITIVITY
from app.research.review_switch import APPROVED_STATUS
from app.retrieval.citation_access import (
    CONCEPT_SUBJECT,
    cited_for_readers,
    filed_for_readers,
    held_claim,
    reader_fact,
)

from . import knowledge_view

__all__ = [
    "HELD",
    "HIDDEN_CONCEPT",
    "HIDDEN_REASONS",
    "NO_SHOWN_SOURCE",
    "RESTRICTED_FACT",
    "UNEXPLAINED",
    "CraftHidden",
    "craft_hidden",
    "hidden_reasons",
    "shown_to_readers",
]

HELD, RESTRICTED_FACT, HIDDEN_CONCEPT, NO_SHOWN_SOURCE = HIDDEN_REASONS = (
    "HELD",
    "RESTRICTED_FACT",
    "HIDDEN_CONCEPT",
    "NO_SHOWN_SOURCE",
)
UNEXPLAINED = "UNEXPLAINED"
VIEWS_PER_BATCH = 2000


@dataclass(frozen=True)
class CraftHidden:
    slug: str
    approved: int
    hidden: Mapping[str, int] = field(default_factory=dict)
    unexplained: tuple[uuid.UUID, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "craft": self.slug,
            "approved": self.approved,
            "hidden": dict(sorted(self.hidden.items())),
            "unexplained": [str(claim_id) for claim_id in self.unexplained],
        }


async def shown_to_readers(session: AsyncSession, claim_ids: Iterable[uuid.UUID]) -> frozenset[uuid.UUID]:
    wanted = list(dict.fromkeys(claim_ids))
    if not wanted:
        return frozenset()
    rows = await session.scalars(select(Claim.id).where(Claim.id.in_(wanted), *reader_fact()))
    return frozenset(rows.all())


async def hidden_reasons(session: AsyncSession, claim_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]:
    wanted = list(dict.fromkeys(claim_ids))
    if not wanted:
        return {}
    rows = await session.execute(select(Claim.id, hidden_reason()).where(Claim.id.in_(wanted)))
    return {claim_id: reason for claim_id, reason in rows.tuples().all() if reason is not None}


def hidden_reason() -> ColumnElement[str | None]:
    return case(
        (Claim.sensitivity != VISIBLE_SENSITIVITY, RESTRICTED_FACT),
        (~filed_for_readers(), HIDDEN_CONCEPT),
        (~cited_for_readers(), NO_SHOWN_SOURCE),
        (held_claim(), HELD),
        else_=None,
    )


async def craft_hidden(session: AsyncSession) -> list[CraftHidden]:
    rows = await session.execute(
        select(Craft.slug, Claim.id, hidden_reason())
        .select_from(Claim)
        .join(Concept, and_(Claim.subjectType == CONCEPT_SUBJECT, Concept.id == Claim.subjectId))
        .join(Craft, Craft.id == Concept.craftId)
        .where(Claim.status == APPROVED_STATUS)
        .order_by(Craft.slug, Claim.id)
    )
    approved: Counter[str] = Counter()
    hidden: dict[str, Counter[str]] = defaultdict(Counter)
    shown: dict[str, list[uuid.UUID]] = defaultdict(list)
    for slug, claim_id, reason in rows.tuples().all():
        approved[slug] += 1
        if reason is None:
            shown[slug].append(claim_id)
        else:
            hidden[slug][reason] += 1
    unexplained = await _unexplained(session, shown)
    return [
        CraftHidden(slug, count, dict(hidden.get(slug, {})), tuple(unexplained.get(slug, ())))
        for slug, count in sorted(approved.items())
        if slug in hidden or slug in unexplained
    ]


async def _unexplained(
    session: AsyncSession, shown: Mapping[str, list[uuid.UUID]]
) -> dict[str, list[uuid.UUID]]:
    every = [claim_id for ids in shown.values() for claim_id in ids]
    seen: set[uuid.UUID] = set()
    for batch in batched(every, VIEWS_PER_BATCH, strict=False):
        views, _ = await knowledge_view.claims_by_id(session, batch, acls=OPEN_CHUNK_ACLS)
        seen.update(views)
    missing = {slug: [claim_id for claim_id in ids if claim_id not in seen] for slug, ids in shown.items()}
    return {slug: ids for slug, ids in missing.items() if ids}
