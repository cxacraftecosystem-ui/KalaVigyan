from __future__ import annotations

from collections.abc import Sequence

from app.research.craft_page import OverviewSection, PageEvent
from app.research.craft_parts import RecordEntry, RecordPart
from app.research.gi_registry import GiFields

from .builder_evidence import fact_sentence
from .chapter_context import ChapterContext
from .chapter_draft import ChapterDraft, Drafted
from .chapter_plates import PicturePlan
from .chapter_prose import prose_blocks
from .market_builder import market_block
from .market_store import GiRecordOffer, MarketOffers, PriceOffer

__all__ = ["market_chapter"]

KEY = "market"
EVENT_LABELS = {"PRICE": "Price", "WORKFORCE": "Workforce"}


def market_chapter(
    ctx: ChapterContext, sections: Sequence[OverviewSection], plan: PicturePlan, events: Sequence[PageEvent]
) -> ChapterDraft:
    items = [Drafted.of_block(block) for block in prose_blocks(ctx, KEY, sections)]
    block = market_block(_offers(ctx), block_id="market.gi")
    if block is not None:
        items.append(Drafted.of_block(block, figure={"craft": ctx.craft_name}))
    record = _record(ctx, [event for event in events if event.kind in EVENT_LABELS])
    if record is not None:
        items.append(Drafted.of_part(record))
    return ChapterDraft(KEY, plan.opener(KEY), items)


def _offers(ctx: ChapterContext) -> MarketOffers:
    market = ctx.records.market
    gi = market.gi
    record = None
    if gi is not None:
        fields = GiFields(
            application_number=gi.application_number,
            certificate_number=gi.certificate_number,
            filed_on=gi.filed_on,
            registered_on=gi.registered_on,
            journal_issue=gi.journal_issue,
            proprietors=gi.proprietors,
            authorised_user_count=gi.authorised_user_count,
        )
        record = GiRecordOffer(fields=fields, claim_ids=gi.claim_ids, imitation=gi.imitation_claim_ids)
    prices = tuple(
        PriceOffer(
            claim_id=price.claim_id, priced_on=price.priced_on, place=price.place_name, district_lgd=None
        )
        for price in market.prices
    )
    views = {view.id: view for view in ctx.records.views if view.id in ctx.own}
    return MarketOffers(
        craft=ctx.records.process.craft,
        record=record,
        prices=prices,
        candidates=tuple(views),
        views=views,
        sources=dict(ctx.records.sources),
    )


def _record(ctx: ChapterContext, events: Sequence[PageEvent]) -> RecordPart | None:
    entries = []
    for event in events:
        fact = ctx.known(event.claim_ids[0])
        if fact is None:
            continue
        label = event.date or EVENT_LABELS[event.kind]
        sentence = fact_sentence(fact, f"market.row{len(entries) + 1}")
        entries.append(
            RecordEntry(
                label=label,
                start=event.start,
                end=event.end,
                factor=None,
                place=None,
                sentences=[sentence],
                plate=None,
            )
        )
    return RecordPart(kind="record", entries=entries) if entries else None
