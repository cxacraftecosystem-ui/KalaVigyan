from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from app.composer.timeline_map import (
    TimelineBrief,
    TimelineChoice,
    TimelinePointChoice,
    TimelineRouteChoice,
    TimelineStatement,
)
from app.research.blocks import named_in, stated_texts
from app.research.blocks_journey import (
    TIMELINE_UNDATED_MAX,
    TimelineMapBlock,
    TimelinePlace,
    TimelinePoint,
    TimelineRoute,
    TimelineUndated,
)
from app.research.datasets import BOUNDARY_CAPTION, DatasetRef
from app.research.explainer import Block
from app.research.timeline import YearSpan, states_movement, years_offered
from app.science.records import KnownClaim

from .answer_events import CitedClaims
from .builder_evidence import fact_sentence, section_facts
from .place_register import RegisterPoint, register_district
from .stated_names import register_places
from .supply_links import OriginPlace
from .supply_places import NamedPlace, stated_words

__all__ = [
    "TIMELINE_POINTS_MAX",
    "TIMELINE_QUOTES_MAX",
    "TIMELINE_ROUTES_MAX",
    "TIMELINE_STATEMENTS_MAX",
    "DatedStatement",
    "ShownPlace",
    "TimelineEntries",
    "TimelineEntry",
    "TimelineOffer",
    "UndatedEntry",
    "timeline_block",
    "timeline_entries",
    "timeline_offer",
]

logger = logging.getLogger(__name__)

TIMELINE_STATEMENTS_MAX = 12
TIMELINE_POINTS_MAX = 10
TIMELINE_ROUTES_MAX = 6
TIMELINE_QUOTES_MAX = 3
REGISTER_VERSION = 2
FIRST_VERSION = 1

ShownPlace = OriginPlace | RegisterPoint


@dataclass(frozen=True)
class DatedStatement:
    claim: KnownClaim
    years: Mapping[str, YearSpan]

    def names(self, place: str) -> bool:
        return named_in(place, fact_sentence(self.claim, "offered"))

    def texts(self) -> list[str]:
        return stated_texts(fact_sentence(self.claim, "offered"))


@dataclass(frozen=True)
class TimelineOffer:
    statements: Mapping[str, DatedStatement]
    undated: tuple[KnownClaim, ...] = ()

    def brief(self) -> TimelineBrief:
        return TimelineBrief(tuple(_brief_statement(ref, dated) for ref, dated in self.statements.items()))


@dataclass(frozen=True)
class TimelineEntry:
    names: tuple[str, ...]
    years: YearSpan
    claim: KnownClaim


@dataclass(frozen=True)
class UndatedEntry:
    name: str | None
    claim: KnownClaim

    @property
    def names(self) -> tuple[str, ...]:
        return (self.name,) if self.name else ()


@dataclass(frozen=True)
class TimelineEntries:
    points: tuple[TimelineEntry, ...]
    routes: tuple[TimelineEntry, ...]
    undated: tuple[UndatedEntry, ...] = ()

    def places(self) -> dict[str, NamedPlace]:
        shown: dict[str, str] = {}
        words: dict[str, frozenset[str]] = {}
        for entry in (*self.points, *self.routes, *self.undated):
            texts = stated_texts(fact_sentence(entry.claim, "placed"))
            for name in entry.names:
                key = name.casefold()
                shown.setdefault(key, name)
                words[key] = words.get(key, frozenset()) | stated_words(texts, (shown[key],))
        return {key: (name, words[key]) for key, name in shown.items()}


def timeline_offer(blocks: Sequence[Block], cited: CitedClaims) -> TimelineOffer | None:
    dated: dict[str, DatedStatement] = {}
    undated: list[KnownClaim] = []
    for claim in section_facts(blocks, cited):
        spans = sorted(years_offered(stated_texts(fact_sentence(claim, "offered"))))
        if spans and len(dated) < TIMELINE_STATEMENTS_MAX:
            years = {f"y{n}": span for n, span in enumerate(spans, start=1)}
            dated[f"c{len(dated) + 1}"] = DatedStatement(claim, years)
        elif not spans and len(undated) < TIMELINE_UNDATED_MAX:
            undated.append(claim)
    return TimelineOffer(dated, tuple(undated)) if dated else None


def timeline_entries(offer: TimelineOffer, choice: TimelineChoice) -> TimelineEntries:
    points: dict[str, TimelineEntry] = {}
    for point in choice.points:
        entry = _point(offer, point) if point.statement not in points else None
        if entry is not None and len(points) < TIMELINE_POINTS_MAX:
            points[point.statement] = entry
    routes: dict[str, TimelineEntry] = {}
    for route in choice.routes:
        entry = _route(offer, route) if route.statement not in routes else None
        if entry is not None and len(routes) < TIMELINE_ROUTES_MAX:
            routes[route.statement] = entry
    ordered = sorted(points.values(), key=lambda entry: entry.years)
    named = [name for entry in (*ordered, *routes.values()) for name in entry.names]
    undated = tuple(UndatedEntry(_undated_place(claim, named), claim) for claim in offer.undated)
    return TimelineEntries(tuple(ordered), tuple(routes.values()), undated)


def timeline_block(
    entries: TimelineEntries, places: Mapping[str, ShownPlace], boundary: DatasetRef, *, block_id: str
) -> TimelineMapBlock | None:
    if not entries.points and not entries.routes:
        return None
    named = entries.places()
    index = {key: n for n, key in enumerate(named)}
    first_route = len(entries.points) + 1
    first_undated = first_route + len(entries.routes)
    shown = [_place(name, places.get(key)) for key, (name, _) in named.items()]
    try:
        return TimelineMapBlock(
            id=block_id,
            kind="timeline_map",
            version=REGISTER_VERSION if entries.undated or _registered(shown) else FIRST_VERSION,
            reuse=None,
            places=shown,
            points=[
                _timeline_point(entry, index, f"{block_id}.{n}")
                for n, entry in enumerate(entries.points, start=1)
            ],
            routes=[
                _timeline_route(entry, index, f"{block_id}.{n}")
                for n, entry in enumerate(entries.routes, start=first_route)
            ],
            undated=[
                _undated(entry, index, f"{block_id}.{n}")
                for n, entry in enumerate(entries.undated, start=first_undated)
            ],
            datasets=[boundary],
            boundary_caption=BOUNDARY_CAPTION,
        )
    except ValidationError as refused:
        logger.warning("the timeline %s is refused: %s", block_id, refused)
        return None


def _point(offer: TimelineOffer, choice: TimelinePointChoice) -> TimelineEntry | None:
    dated = offer.statements.get(choice.statement)
    years = dated.years.get(choice.years) if dated is not None else None
    place = choice.place.strip()
    if dated is None or years is None:
        logger.info("the timeline drops point %r: its statement or years were not offered", choice.statement)
        return None
    if not dated.names(place):
        logger.info("the timeline drops %r: statement %s does not name it", place, choice.statement)
        return None
    return TimelineEntry((place,), years, dated.claim)


def _route(offer: TimelineOffer, choice: TimelineRouteChoice) -> TimelineEntry | None:
    dated = offer.statements.get(choice.statement)
    years = dated.years.get(choice.years) if dated is not None else None
    start, end = choice.start.strip(), choice.end.strip()
    if dated is None or years is None:
        logger.info("the timeline drops route %r: its statement or years were not offered", choice.statement)
        return None
    if start.casefold() == end.casefold() or not states_movement(dated.texts(), start, end):
        logger.info("the timeline drops a route from %r to %r: no text states the move", start, end)
        return None
    return TimelineEntry((start, end), years, dated.claim)


def _place(name: str, place: ShownPlace | None) -> TimelinePlace:
    if place is None:
        return TimelinePlace(name=name, wikidata_id=None, latitude=None, longitude=None)
    if isinstance(place, RegisterPoint):
        return TimelinePlace(
            name=name,
            wikidata_id=None,
            latitude=place.latitude,
            longitude=place.longitude,
            district_lgd=place.district_lgd,
        )
    return TimelinePlace(
        name=name, wikidata_id=place.wikidata_id, latitude=place.latitude, longitude=place.longitude
    )


def _registered(places: Sequence[TimelinePlace]) -> bool:
    return any(place.district_lgd is not None for place in places)


def _undated_place(claim: KnownClaim, named: Sequence[str]) -> str | None:
    sentence = fact_sentence(claim, "undated")
    shown = next((name for name in named if named_in(name, sentence)), None)
    if shown is not None:
        return shown
    written = (place.written for place in register_places(claim.text))
    return next((name for name in written if register_district(name) is not None), None)


def _undated(entry: UndatedEntry, index: Mapping[str, int], sentence_id: str) -> TimelineUndated:
    place = index[entry.name.casefold()] if entry.name else None
    return TimelineUndated(place=place, sentence=fact_sentence(entry.claim, sentence_id))


def _timeline_point(entry: TimelineEntry, index: Mapping[str, int], sentence_id: str) -> TimelinePoint:
    year_from, year_to = entry.years
    return TimelinePoint(
        place=index[entry.names[0].casefold()],
        year_from=year_from,
        year_to=year_to,
        sentence=fact_sentence(entry.claim, sentence_id),
    )


def _timeline_route(entry: TimelineEntry, index: Mapping[str, int], sentence_id: str) -> TimelineRoute:
    start, end = (index[name.casefold()] for name in entry.names)
    year_from, year_to = entry.years
    return TimelineRoute(
        start=start,
        end=end,
        year_from=year_from,
        year_to=year_to,
        sentence=fact_sentence(entry.claim, sentence_id),
    )


def _brief_statement(ref: str, dated: DatedStatement) -> TimelineStatement:
    quotes = [c.quote for c in dated.claim.citations if c.quote][:TIMELINE_QUOTES_MAX]
    return TimelineStatement(
        ref=ref,
        text=dated.claim.text,
        quotes=tuple(dict.fromkeys(quotes)),
        years=tuple((year_ref, _shown_span(span)) for year_ref, span in dated.years.items()),
    )


def _shown_span(span: YearSpan) -> str:
    return str(span[0]) if span[0] == span[1] else f"{span[0]} to {span[1]}"
