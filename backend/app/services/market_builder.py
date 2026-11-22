from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import replace

from pydantic import ValidationError

from app.research.blocks import ExplainerSentence, stated_texts
from app.research.blocks_insight import GiStatus, MarketGiBlock, PriceRange
from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.research.gi_registry import (
    IMITATION_SOURCE_KINDS,
    REGISTRY_SOURCE_KINDS,
    GiFields,
    gi_fields,
    gi_status_name,
    merged_fields,
    names_registry,
    states_imitation,
)
from app.research.offered_facts import fact_rank
from app.research.stated_dates import stated_precision
from app.research.stated_prices import StatedPrice, stated_prices
from app.science.records import KnownClaim

from .builder_evidence import fact_sentence, known_fact, sources_beyond
from .builder_interface import BuildAsk, BuilderTools, Built
from .market_store import MarketOffers, PriceOffer, market_offers

__all__ = [
    "GI_FIELD",
    "GI_PARTS",
    "IMITATION_MAX",
    "MARKET_FIELDS",
    "MARKET_PARTS",
    "PRICES_MAX",
    "PRICE_FIELD",
    "PRICE_PARTS",
    "MarketGiBuilder",
    "MarketLoader",
    "market_block",
    "section_parts",
]

logger = logging.getLogger(__name__)

GI_FIELD = "POLICY"
PRICE_FIELD = "ECONOMICS"
MARKET_FIELDS = frozenset({PRICE_FIELD, GI_FIELD})
GI_PARTS = frozenset({"gi", "imitation"})
PRICE_PARTS = frozenset({"prices"})
MARKET_PARTS = GI_PARTS | PRICE_PARTS
IMITATION_MAX = 3
PRICES_MAX = 6
MARKET_BLOCK_PREFIX = "market"

MarketLoader = Callable[[Sequence[CraftRef]], Awaitable[Sequence[MarketOffers]]]


class MarketGiBuilder:
    def __init__(self, tools: BuilderTools, *, offers: MarketLoader | None = None) -> None:
        self._offers = offers or _stored_markets(tools)

    async def build(self, ask: BuildAsk) -> Built:
        lead = ask.request.craft
        if lead is None:
            return Built()
        shown = {block.craft.slug for block in ask.blocks if isinstance(block, MarketGiBlock)}
        parts = section_parts(ask.section.discipline, ask.answer_fields)
        found = await self._offers((lead, *ask.request.compared))
        blocks: list[MarketGiBlock] = []
        sources: dict[str, SourceRef] = {}
        for number, offers in enumerate(found, start=1):
            if offers.craft.slug in shown:
                continue
            block_id = f"{ask.section.id}.{MARKET_BLOCK_PREFIX}{number}"
            block = market_block(offers, block_id=block_id, parts=parts)
            if block is not None:
                blocks.append(block)
                sources.update(offers.sources)
        return Built(tuple(blocks), sources_beyond(blocks, sources, ask.cited))


def section_parts(discipline: str, answer_fields: Collection[str]) -> frozenset[str]:
    if not {GI_FIELD, PRICE_FIELD} <= set(answer_fields):
        return MARKET_PARTS
    return GI_PARTS if discipline == GI_FIELD else PRICE_PARTS


def market_block(
    offers: MarketOffers, *, block_id: str, parts: frozenset[str] = MARKET_PARTS
) -> MarketGiBlock | None:
    facts = {claim_id: fact for claim_id, view in offers.views.items() if (fact := known_fact(view))}
    gi = _gi_status(offers, facts, block_id) if "gi" in parts else None
    shown = _claim_ids(gi.sentences if gi else [])
    priced = {price.claim_id for price in offers.prices}
    numbered = len(gi.sentences) if gi else 0
    imitation = _imitation(offers, facts, shown | priced, block_id, numbered) if "imitation" in parts else []
    prices = _price_ranges(offers, facts, block_id, numbered + len(imitation)) if "prices" in parts else []
    if gi is None and not imitation and not prices:
        return None
    try:
        return MarketGiBlock(
            id=block_id,
            kind="market_gi",
            version=1,
            reuse=None,
            craft=offers.craft,
            gi=gi,
            imitation=imitation,
            prices=prices,
        )
    except ValidationError as refused:
        logger.warning("the market block of %s is not shown: %s", offers.craft.slug, refused)
        return None


def _gi_status(offers: MarketOffers, facts: Mapping[uuid.UUID, KnownClaim], block_id: str) -> GiStatus | None:
    if offers.record is not None:
        claims = [facts[c] for c in offers.record.claim_ids if c in facts and _registry(facts[c], offers)]
        status = _status(offers.record.fields, _ranked(claims, offers.sources), block_id)
        if status is None:
            logger.warning("the GI record of %s is not shown: its claims do not state it", offers.craft.slug)
        return status
    read: list[tuple[KnownClaim, GiFields]] = []
    for claim_id in offers.candidates:
        claim = facts.get(claim_id)
        if claim is None or not names_registry(claim.text) or not _registry(claim, offers):
            continue
        found = gi_fields(_stated(claim))
        if found is not None and found.stated():
            read.append((claim, found))
    merged = merged_fields(found for _, found in read)
    if not read or merged is None:
        return None
    return _status(merged, _ranked([claim for claim, _ in read], offers.sources), block_id)


def _status(read: GiFields, claims: Sequence[KnownClaim], block_id: str) -> GiStatus | None:
    sentences = [fact_sentence(claim, f"{block_id}.{n}") for n, claim in enumerate(claims, start=1)]
    texts = [text for sentence in sentences for text in stated_texts(sentence)]
    fields = _dated_as_stated(read, texts)
    name = gi_status_name(fields, texts)
    if name is None or not sentences:
        return None
    try:
        return GiStatus(
            status=name,
            application_number=fields.application_number,
            certificate_number=fields.certificate_number,
            filed_on=fields.filed_on,
            registered_on=fields.registered_on,
            journal_issue=fields.journal_issue,
            proprietors=list(fields.proprietors),
            authorised_user_count=fields.authorised_user_count,
            sentences=sentences,
        )
    except ValidationError as refused:
        logger.info("a GI status is not shown: %s", refused)
        return None


def _imitation(
    offers: MarketOffers,
    facts: Mapping[uuid.UUID, KnownClaim],
    used: Collection[uuid.UUID],
    block_id: str,
    numbered: int,
) -> list[ExplainerSentence]:
    signs = [
        facts[claim_id]
        for claim_id in offers.candidates
        if claim_id in facts
        and claim_id not in used
        and states_imitation(facts[claim_id].text)
        and _cites_any(facts[claim_id], IMITATION_SOURCE_KINDS, offers.sources)
    ]
    chosen = _ranked(signs, offers.sources)[:IMITATION_MAX]
    return [fact_sentence(claim, f"{block_id}.{numbered + n}") for n, claim in enumerate(chosen, start=1)]


def _price_ranges(
    offers: MarketOffers, facts: Mapping[uuid.UUID, KnownClaim], block_id: str, numbered: int
) -> list[PriceRange]:
    ranges: list[PriceRange] = []
    for offer in offers.prices:
        claim = facts.get(offer.claim_id)
        if claim is None or offer.priced_on is None or offer.place is None:
            continue
        for price in stated_prices(claim.text):
            sentence = fact_sentence(claim, f"{block_id}.{numbered + len(ranges) + 1}")
            built = _price_range(price, offer, sentence)
            if built is not None:
                ranges.append(built)
            if len(ranges) == PRICES_MAX:
                return ranges
    return ranges


def _price_range(price: StatedPrice, offer: PriceOffer, sentence: ExplainerSentence) -> PriceRange | None:
    priced_on = stated_precision(offer.priced_on, stated_texts(sentence)) if offer.priced_on else None
    if priced_on is None:
        logger.info(
            "a price of %s is not shown: its sentence states no date it was priced on", offer.claim_id
        )
        return None
    try:
        return PriceRange(
            stated=price.stated,
            low=float(price.low),
            high=None if price.high is None else float(price.high),
            currency=price.currency,
            scale=price.scale,
            per=price.per,
            priced_on=priced_on,
            place=offer.place,
            district_lgd=offer.district_lgd,
            sentence=sentence,
        )
    except ValidationError as refused:
        logger.info("a price is not shown: %s", refused)
        return None


def _dated_as_stated(fields: GiFields, texts: Sequence[str]) -> GiFields:
    return replace(
        fields,
        filed_on=stated_precision(fields.filed_on, texts) if fields.filed_on else None,
        registered_on=stated_precision(fields.registered_on, texts) if fields.registered_on else None,
    )


def _registry(claim: KnownClaim, offers: MarketOffers) -> bool:
    kinds = [_kind(citation.source_id, offers.sources) for citation in claim.citations]
    return bool(kinds) and all(kind in REGISTRY_SOURCE_KINDS for kind in kinds)


def _cites_any(claim: KnownClaim, wanted: Collection[str], sources: Mapping[str, SourceRef]) -> bool:
    return any(_kind(citation.source_id, sources) in wanted for citation in claim.citations)


def _kind(source_id: str, sources: Mapping[str, SourceRef]) -> str | None:
    source = sources.get(source_id)
    return None if source is None else source.kind


def _stated(claim: KnownClaim) -> list[str]:
    return [claim.text, *(citation.quote for citation in claim.citations if citation.quote)]


def _ranked(claims: Iterable[KnownClaim], sources: Mapping[str, SourceRef]) -> list[KnownClaim]:
    return sorted(claims, key=lambda claim: fact_rank(fact_sentence(claim, "rank"), sources))


def _claim_ids(sentences: Iterable[ExplainerSentence]) -> set[uuid.UUID]:
    return {uuid.UUID(citation.claim_id) for sentence in sentences for citation in sentence.citations}


def _stored_markets(tools: BuilderTools) -> MarketLoader:
    async def load(crafts: Sequence[CraftRef]) -> Sequence[MarketOffers]:
        async with tools.sessions() as session:
            return await market_offers(session, crafts)

    return load
