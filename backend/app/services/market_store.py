from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, ClaimSource, Concept, Craft, CraftGiRecord, CraftPrice, Source
from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.research.gi_registry import MARKET_PREFILTER_WORDS, REGISTRY_SOURCE_KINDS, GiFields
from app.research.retrieval import EVERY_CHUNK_ACLS
from app.research.stated_prices import stated_prices
from app.research.timeline import years_offered
from app.research.vocabulary import FACT_LEVELS

from . import knowledge_view
from .knowledge_view import ClaimView
from .learning_facts import source_refs
from .place_register import register_district
from .stated_names import register_places

__all__ = [
    "MARKET_CANDIDATES_MAX",
    "GiRecordOffer",
    "MarketOffers",
    "PriceOffer",
    "market_offers",
    "stated_price_offer",
]

MARKET_CANDIDATES_MAX = 80
STATED_PRICE_CLAIMS_MAX = 40
PRICE_PATTERN = r"(₹|\mrs\.?\s*[0-9]|\minr\s*[0-9]|[0-9]\s*rupees?\M)"
CONCEPT_SUBJECT = "CONCEPT"


@dataclass(frozen=True)
class GiRecordOffer:
    fields: GiFields
    claim_ids: tuple[uuid.UUID, ...]
    imitation: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True)
class PriceOffer:
    claim_id: uuid.UUID
    priced_on: str | None
    place: str | None
    district_lgd: int | None


@dataclass(frozen=True)
class MarketOffers:
    craft: CraftRef
    record: GiRecordOffer | None = None
    prices: tuple[PriceOffer, ...] = ()
    candidates: tuple[uuid.UUID, ...] = ()
    views: Mapping[uuid.UUID, ClaimView] = field(default_factory=dict)
    sources: Mapping[str, SourceRef] = field(default_factory=dict)


async def market_offers(session: AsyncSession, crafts: Sequence[CraftRef]) -> list[MarketOffers]:
    found: list[MarketOffers] = []
    for ref in crafts:
        craft = await knowledge_view.resolve_craft(session, ref.slug)
        if craft is not None:
            found.append(await _craft_offers(session, craft))
    return found


async def _craft_offers(session: AsyncSession, craft: Craft) -> MarketOffers:
    record = await _gi_record(session, craft.id)
    prices = await _prices(session, craft.id)
    candidates = await _registry_claims(session, craft.id)
    priced = () if prices else await _price_claims(session, craft.id)
    wanted = [
        *(record.claim_ids if record else ()),
        *(record.imitation if record else ()),
        *(price.claim_id for price in prices),
        *candidates,
        *priced,
    ]
    views, sources = await knowledge_view.claims_by_id(session, wanted, acls=EVERY_CHUNK_ACLS)
    stated = [offer for claim_id in priced if claim_id in views and (offer := _stated(views[claim_id]))]
    return MarketOffers(
        craft=CraftRef.model_validate(knowledge_view.craft_ref(craft)),
        record=record,
        prices=prices or tuple(stated),
        candidates=candidates,
        views=views,
        sources=source_refs(sources),
    )


async def _gi_record(session: AsyncSession, craft_id: uuid.UUID) -> GiRecordOffer | None:
    row = await session.get(CraftGiRecord, craft_id)
    if row is None:
        return None
    fields = GiFields(
        application_number=row.applicationNumber,
        certificate_number=row.certificateNumber,
        filed_on=row.filedOn,
        registered_on=row.registeredOn,
        journal_issue=row.journalIssue,
        proprietors=tuple(row.proprietors),
        authorised_user_count=row.authorisedUserCount,
    )
    return GiRecordOffer(fields=fields, claim_ids=tuple(row.claimIds), imitation=tuple(row.imitationClaimIds))


async def _prices(session: AsyncSession, craft_id: uuid.UUID) -> tuple[PriceOffer, ...]:
    rows = await session.execute(
        select(CraftPrice.claimId, CraftPrice.pricedOn, CraftPrice.placeName, CraftPrice.districtLgd)
        .where(CraftPrice.craftId == craft_id)
        .order_by(CraftPrice.pricedOn.desc(), CraftPrice.claimId, CraftPrice.placeName)
    )
    return tuple(
        PriceOffer(
            claim_id=row.claimId, priced_on=row.pricedOn, place=row.placeName, district_lgd=row.districtLgd
        )
        for row in rows.all()
    )


async def _registry_claims(session: AsyncSession, craft_id: uuid.UUID) -> tuple[uuid.UUID, ...]:
    owned = select(Concept.id).where(Concept.craftId == craft_id)
    statement = (
        select(Claim.id)
        .join(ClaimSource, ClaimSource.claimId == Claim.id)
        .join(Source, Source.id == ClaimSource.sourceId)
        .where(
            Claim.subjectType == CONCEPT_SUBJECT,
            Claim.subjectId.in_(owned),
            Source.kind.in_(REGISTRY_SOURCE_KINDS),
            or_(*(Claim.text.ilike(f"%{word}%") for word in MARKET_PREFILTER_WORDS)),
        )
        .distinct()
        .order_by(Claim.id)
        .limit(MARKET_CANDIDATES_MAX)
    )
    return tuple((await session.scalars(statement)).all())


def stated_price_offer(claim_id: uuid.UUID, text: str) -> PriceOffer | None:
    years = years_offered([text])
    districts = [
        (place.written, lgd)
        for place in register_places(text)
        if (lgd := register_district(place.written)) is not None
    ]
    if len(stated_prices(text)) != 1 or len(years) != 1 or len(districts) != 1:
        return None
    (start, end), (place, district_lgd) = next(iter(years)), districts[0]
    if start != end:
        return None
    return PriceOffer(claim_id=claim_id, priced_on=str(start), place=place, district_lgd=district_lgd)


def _stated(view: ClaimView) -> PriceOffer | None:
    return stated_price_offer(view.id, view.text) if view.level in FACT_LEVELS else None


async def _price_claims(session: AsyncSession, craft_id: uuid.UUID) -> tuple[uuid.UUID, ...]:
    owned = select(Concept.id).where(Concept.craftId == craft_id)
    statement = (
        select(Claim.id)
        .where(
            Claim.subjectType == CONCEPT_SUBJECT,
            Claim.subjectId.in_(owned),
            Claim.text.op("~*")(PRICE_PATTERN),
        )
        .order_by(Claim.id)
        .limit(STATED_PRICE_CLAIMS_MAX)
    )
    return tuple((await session.scalars(statement)).all())
