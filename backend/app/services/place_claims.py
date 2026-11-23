from __future__ import annotations

import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Craft, Source
from app.research.blocks import named_in_texts
from app.research.blocks_place import DistrictRef
from app.research.calendar import regional_month_months, season_months
from app.research.retrieval import EVERY_CHUNK_ACLS
from app.science.records import KnownClaim

from .builder_evidence import known_fact
from .builder_interface import SourceRefs
from .curation_keys import DISCIPLINE_CONCEPT_TYPES
from .knowledge_view import ClaimView, claims_for, source_ref

__all__ = [
    "PLACE_CLAIMS_MAX",
    "PLACE_CONCEPT_TYPE",
    "PlaceAsk",
    "PlaceClaims",
    "district_place_claims",
    "place_calendar_claims",
    "ranked_place_views",
    "states_a_calendar",
]

PLACE_CLAIMS_MAX = 6
PLACE_CONCEPT_TYPE = DISCIPLINE_CONCEPT_TYPES["GEOGRAPHY"]


@dataclass(frozen=True)
class PlaceClaims:
    claims: tuple[KnownClaim, ...] = ()
    sources: SourceRefs = field(default_factory=dict)


@dataclass(frozen=True)
class PlaceAsk:
    question: str
    mode: str
    held: Collection[uuid.UUID] = ()


async def district_place_claims(
    session: AsyncSession, craft: Craft, districts: Sequence[DistrictRef], ask: PlaceAsk
) -> PlaceClaims:
    views, sources = await claims_for(
        session, craft, mode=ask.mode, question=ask.question, acls=EVERY_CHUNK_ACLS
    )
    chosen = ranked_place_views(views, districts, held=ask.held)[:PLACE_CLAIMS_MAX]
    return _with_sources([fact for view in chosen if (fact := known_fact(view)) is not None], sources)


async def place_calendar_claims(session: AsyncSession, craft: Craft, *, mode: str) -> PlaceClaims:
    views, sources = await claims_for(session, craft, mode=mode, acls=EVERY_CHUNK_ACLS)
    placed = [view for view in views if view.concept_type == PLACE_CONCEPT_TYPE]
    facts = [fact for view in placed if (fact := known_fact(view)) is not None and states_a_calendar(fact)]
    return _with_sources(facts, sources)


def states_a_calendar(claim: KnownClaim) -> bool:
    quotes = [citation.quote for citation in claim.citations if citation.quote]
    return any(season_months(quote) or regional_month_months(quote) for quote in quotes)


def ranked_place_views(
    views: Sequence[ClaimView], districts: Sequence[DistrictRef], *, held: Collection[uuid.UUID] = ()
) -> list[ClaimView]:
    names = [name for district in districts for name in district.names()]
    placed = [view for view in views if view.concept_type == PLACE_CONCEPT_TYPE and view.id not in held]
    return sorted(placed, key=lambda view: (not _names_any(view, names), -view.rank, view.text))


def _with_sources(facts: Sequence[KnownClaim], sources: Mapping[uuid.UUID, Source]) -> PlaceClaims:
    cited = {citation.source_id for fact in facts for citation in fact.citations}
    refs = {str(sid): source_ref(source) for sid, source in sources.items() if str(sid) in cited}
    return PlaceClaims(tuple(facts), refs)


def _names_any(view: ClaimView, names: Sequence[str]) -> bool:
    texts = [view.text, *(str(citation.get("quote") or "") for citation in view.citations)]
    return any(named_in_texts(name, texts) for name in names)
