import asyncio
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from app.research.retrieval import ClaimHit, KnowledgeHits, KnowledgeQuery
from app.services.answer_events import CitedClaims, joined_claims
from app.services.knowledge_view import ClaimView

from .fakes import FakeStore

__all__ = ["LedeStore", "StoredSearch", "claim_hit"]


@dataclass
class LedeStore(FakeStore):
    async def cited(self, claim_ids: Iterable[uuid.UUID]) -> CitedClaims:
        wanted = list(claim_ids)
        known = await super().cited(wanted)
        held = {claim: view for claim, view in self.stored.views.items() if claim in wanted}
        return joined_claims(known, CitedClaims(views=held, sources=self.stored.sources))


@dataclass
class StoredSearch:
    store: FakeStore
    order: Sequence[uuid.UUID] = ()
    delay: float = 0.0
    queries: list[KnowledgeQuery] = field(default_factory=list)

    async def search(self, query: KnowledgeQuery) -> KnowledgeHits:
        self.queries.append(query)
        await asyncio.sleep(self.delay)
        views = self.store.stored.views
        ranked = [views[claim] for claim in self.order] if self.order else list(views.values())
        hits = tuple(claim_hit(view, rank) for rank, view in enumerate(ranked[: query.limit], start=1))
        return KnowledgeHits(craft_slug=query.craft_slug, claims=hits)


def claim_hit(view: ClaimView, rank: int) -> ClaimHit:
    return ClaimHit(
        claim_id=view.id,
        text=view.text,
        level=view.level,
        subject_type="CONCEPT",
        subject_id=view.concept_id or view.id,
        score=1 / rank,
    )
