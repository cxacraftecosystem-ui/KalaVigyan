from __future__ import annotations

from collections.abc import Sequence

from app.composer.timeline_map import (
    REPLY_POINTS_MAX,
    REPLY_ROUTES_MAX,
    TimelineChoice,
    TimelinePointChoice,
    TimelineRouteChoice,
)
from app.data.district_register import load_district_other_names
from app.research.blocks_journey import TimelineMapBlock
from app.research.craft_page import OverviewSection, PageEvent, PagePlace
from app.research.craft_parts import PlatePart, RecordEntry, RecordPart
from app.research.datasets import BOUNDARY_DATASET_CODE
from app.research.timeline import states_movement, years_offered, years_stated

from .builder_evidence import fact_sentence
from .chapter_context import ChapterContext
from .chapter_draft import ChapterDraft, Drafted
from .chapter_plates import PicturePlan, placed_records
from .chapter_prose import prose_blocks
from .place_points import OriginPlace
from .timeline_story import DatedStatement, TimelineOffer, timeline_block, timeline_entries

__all__ = ["history_chapter", "span_label"]

KEY = "history"
STATED = "STATED"


def history_chapter(
    ctx: ChapterContext,
    sections: Sequence[OverviewSection],
    plan: PicturePlan,
    found: tuple[Sequence[PageEvent], Sequence[PagePlace]],
) -> ChapterDraft:
    events, places = found
    items = [Drafted.of_block(block) for block in prose_blocks(ctx, KEY, sections)]
    timeline = _timeline(ctx, events, places)
    held = (
        {citation.claim_id for sentence in timeline.cited_sentences() for citation in sentence.citations}
        if timeline
        else set()
    )
    if timeline is not None:
        years = sorted(year for point in timeline.points for year in (point.year_from, point.year_to))
        years += sorted(year for route in timeline.routes for year in (route.year_from, route.year_to))
        values = {"craft": ctx.craft_name, "first": min(years), "last": max(years)}
        items.append(Drafted.of_block(timeline, figure=values))
    dated = _dated(
        ctx, [event for event in events if event.kind == STATED and str(event.claim_ids[0]) not in held]
    )
    record, loose = placed_records(plan, KEY, dated)
    if record is not None:
        items.append(Drafted.of_part(record))
    items += [Drafted.of_part(plate) for plate in loose]
    items += [Drafted.of_part(PlatePart(kind="plate", plate=p.plate)) for p in plan.plates(KEY)]
    return ChapterDraft(KEY, plan.opener(KEY), items)


def span_label(start: int, end: int, texts: Sequence[str] = ()) -> str:
    stated = years_stated(texts).get((start, end))
    if stated is not None:
        return stated
    return str(start) if start == end else f"{start} to {end}"


def _timeline(
    ctx: ChapterContext, events: Sequence[PageEvent], places: Sequence[PagePlace]
) -> TimelineMapBlock | None:
    boundary = ctx.rows.datasets.get(BOUNDARY_DATASET_CODE)
    if boundary is None:
        return None
    names = list(
        dict.fromkeys(
            [*(place.name for place in places), *(name for place in places for name in _names(place))]
        )
    )
    statements: dict[str, DatedStatement] = {}
    points, routes = [], []
    for event in events:
        if event.kind != STATED:
            continue
        fact = ctx.known(event.claim_ids[0])
        if fact is None:
            continue
        dated = DatedStatement(fact, {"y1": (event.start, event.end)})
        ref = f"c{len(statements) + 1}"
        named = [name for name in names if dated.names(name)]
        moves = [(a, b) for a in named for b in named if a != b and states_movement(dated.texts(), a, b)]
        if not named:
            continue
        statements[ref] = dated
        routes += [TimelineRouteChoice(statement=ref, start=a, end=b, years="y1") for a, b in moves[:1]]
        if not moves:
            points.append(TimelinePointChoice(statement=ref, place=named[0], years="y1"))
    if not points and not routes:
        return None
    entries = timeline_entries(TimelineOffer(statements), timeline_choice(points, routes))
    return timeline_block(entries, _placed(ctx, places), boundary, block_id="history.timeline")


def timeline_choice(
    points: Sequence[TimelinePointChoice], routes: Sequence[TimelineRouteChoice]
) -> TimelineChoice:
    return TimelineChoice(points=list(points[:REPLY_POINTS_MAX]), routes=list(routes[:REPLY_ROUTES_MAX]))


def _names(place: PagePlace) -> list[str]:
    found = [place.name]
    if place.district is not None:
        found.append(place.district.name)
        found += load_district_other_names().get(place.district.lgd or 0, ())
    return found


def _placed(ctx: ChapterContext, places: Sequence[PagePlace]) -> dict[str, OriginPlace]:
    found: dict[str, OriginPlace] = {}
    for place in places:
        point = ctx.rows.points.get(place.wikidata_id) if place.wikidata_id else None
        if point is not None:
            found.setdefault(
                place.name.casefold(), OriginPlace(point.wikidata_id, point.latitude, point.longitude)
            )
    return found


def _dated(ctx: ChapterContext, events: Sequence[PageEvent]) -> RecordPart | None:
    entries = []
    for event in events:
        fact = ctx.known(event.claim_ids[0])
        if fact is None or not years_offered([fact.text]):
            continue
        sentence = fact_sentence(fact, f"history.dated{len(entries) + 1}")
        place = None
        entries.append(
            RecordEntry(
                label=span_label(event.start, event.end, [fact.text]),
                start=event.start,
                end=event.end,
                factor=None,
                place=place,
                sentences=[sentence],
                plate=None,
            )
        )
    return RecordPart(kind="record", entries=entries) if entries else None
