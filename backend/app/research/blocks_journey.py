from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from app.models.enums import IMAGE_RELEVANCE

from .base import ContractModel, absent
from .blocks import (
    SENTENCE,
    BlockBase,
    ExplainerSentence,
    SentenceSpec,
    named_in,
    require_facts,
    stated_texts,
)
from .blocks_place import DistrictRef
from .citations import AnswerSentence
from .datasets import BOUNDARY_CAPTION, BOUNDARY_DATASET_CODE, DatasetRef
from .media_refs import MediaRef
from .terms import WIKIDATA_ID_PATTERN
from .timeline import states_movement, years_named

__all__ = [
    "IMAGE_ZOOM_LEVELS",
    "TIMELINE_UNDATED_MAX",
    "ZOOM_LEVELS",
    "TimelineMapBlock",
    "TimelinePlace",
    "TimelinePoint",
    "TimelineRoute",
    "TimelineUndated",
    "ZoomCompound",
    "ZoomLevel",
    "ZoomStoryBlock",
]

ZOOM_LEVELS = ("DISTRICT", "WORKSHOP", "CLOTH", "FIBRE", "MOLECULE")
IMAGE_ZOOM_LEVELS = ("WORKSHOP", "CLOTH", "FIBRE")
TIMELINE_UNDATED_MAX = 6

ZoomLevelName = Literal[*ZOOM_LEVELS]
ImageRelevance = Literal[*IMAGE_RELEVANCE]


class ZoomCompound(ContractModel):
    compound_id: uuid.UUID
    pubchem_cid: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=300)
    formula: str | None = Field(min_length=1, max_length=120)
    source_id: str = Field(min_length=1)


class ZoomLevel(ContractModel):
    level: ZoomLevelName
    sentence: ExplainerSentence
    district: DistrictRef | None
    media: MediaRef | None
    relevance: ImageRelevance | None
    compound: ZoomCompound | None

    @model_validator(mode="after")
    def _real_matter_at_its_scale(self) -> Self:
        shown = {
            "district": self.district is not None,
            "media": self.media is not None,
            "relevance": self.relevance is not None,
            "compound": self.compound is not None,
        }
        wanted = _zoom_fields(self.level)
        if {name for name, present in shown.items() if present} != wanted:
            raise ValueError(f"zoom level {self.level} shows exactly its {' and '.join(sorted(wanted))}")
        if self.media is not None and self.media.display != "INLINE":
            raise ValueError(f"zoom level {self.level} shows only a licensed image, never a link card")
        named = self.district.name if self.district else self.compound.name if self.compound else None
        if named is not None and not named_in(named, self.sentence):
            raise ValueError(f"zoom level {self.level} shows {named!r}, which its sentence does not name")
        return self


class ZoomStoryBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (("levels", [(("sentence", SENTENCE),)]),)

    kind: Literal["zoom_story"]
    version: Literal[1]
    levels: list[ZoomLevel] = Field(min_length=2, max_length=len(ZOOM_LEVELS))
    datasets: list[DatasetRef]
    boundary_caption: str | None

    @model_validator(mode="after")
    def _levels_zoom_in_over_real_geometry(self) -> Self:
        require_facts(f"zoom story {self.id}", [level.sentence for level in self.levels])
        ranks = [ZOOM_LEVELS.index(level.level) for level in self.levels]
        if ranks != sorted(set(ranks)):
            raise ValueError(f"zoom story {self.id} zooms in level by level, each level once")
        mapped = any(level.district is not None for level in self.levels)
        if [dataset.code for dataset in self.datasets] != ([BOUNDARY_DATASET_CODE] if mapped else []):
            raise ValueError(
                f"zoom story {self.id} cites {BOUNDARY_DATASET_CODE} exactly when it maps a district"
            )
        if self.boundary_caption != (BOUNDARY_CAPTION if mapped else None):
            raise ValueError(
                f"zoom story {self.id} carries the boundary caption exactly when it maps a district"
            )
        return self

    def direct_source_ids(self) -> Iterator[str]:
        for level in self.levels:
            if level.compound is not None:
                yield level.compound.source_id

    def cites_datasets(self) -> bool:
        return bool(self.datasets)

    def shown_labels(self) -> list[str]:
        return [_level_label(level) for level in self.levels]


class TimelinePlace(ContractModel):
    name: str = Field(min_length=1, max_length=200)
    wikidata_id: str | None = Field(pattern=WIKIDATA_ID_PATTERN)
    latitude: float | None = Field(ge=-90, le=90)
    longitude: float | None = Field(ge=-180, le=180)
    district_lgd: int | None = Field(default=None, ge=1, exclude_if=absent)

    @model_validator(mode="after")
    def _placed_from_wikidata_or_the_register(self) -> Self:
        placed = (self.latitude is not None, self.longitude is not None)
        named = self.wikidata_id is not None or self.district_lgd is not None
        if placed[0] != placed[1] or (placed[0] and not named):
            raise ValueError(
                f"place {self.name!r} is placed only with both coordinates of its item or district"
            )
        return self


class TimelineUndated(ContractModel):
    place: int | None = Field(ge=0)
    sentence: ExplainerSentence


class TimelinePoint(ContractModel):
    place: int = Field(ge=0)
    year_from: int
    year_to: int
    sentence: ExplainerSentence

    @model_validator(mode="after")
    def _dated_as_its_source_states(self) -> Self:
        _require_stated_years(self.year_from, self.year_to, self.sentence)
        return self


class TimelineRoute(ContractModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    year_from: int
    year_to: int
    sentence: ExplainerSentence

    @model_validator(mode="after")
    def _dated_between_two_places(self) -> Self:
        if self.start == self.end:
            raise ValueError("a route joins two different places")
        _require_stated_years(self.year_from, self.year_to, self.sentence)
        return self


def _none_listed(value: list[TimelineUndated]) -> bool:
    return not value


class TimelineMapBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (
        ("points", [(("sentence", SENTENCE),)]),
        ("routes", [(("sentence", SENTENCE),)]),
        ("undated", [(("sentence", SENTENCE),)]),
    )

    kind: Literal["timeline_map"]
    version: Literal[1, 2]
    places: list[TimelinePlace] = Field(min_length=1)
    points: list[TimelinePoint]
    routes: list[TimelineRoute]
    undated: list[TimelineUndated] = Field(
        default_factory=list, max_length=TIMELINE_UNDATED_MAX, exclude_if=_none_listed
    )
    datasets: list[DatasetRef] = Field(min_length=1, max_length=1)
    boundary_caption: str

    @model_validator(mode="after")
    def _dated_places_and_stated_routes(self) -> Self:
        require_facts(f"timeline {self.id}", list(self.cited_sentences()))
        if self.boundary_caption != BOUNDARY_CAPTION or self.datasets[0].code != BOUNDARY_DATASET_CODE:
            raise ValueError(f"timeline {self.id} draws {BOUNDARY_DATASET_CODE} under the boundary caption")
        problems = _version_problems(self) + _place_problems(
            self.id, self.places, self.points, self.routes, self.undated
        )
        if problems:
            raise ValueError("; ".join(problems))
        names = [place.name for place in self.places]
        if any(not named_in(names[point.place], point.sentence) for point in self.points):
            raise ValueError(f"timeline {self.id} dates only places a point's sentence names")
        if any(
            entry.place is not None and not named_in(names[entry.place], entry.sentence)
            for entry in self.undated
        ):
            raise ValueError(f"timeline {self.id} places an undated sentence only where it names the place")
        for route in self.routes:
            if not states_movement(stated_texts(route.sentence), names[route.start], names[route.end]):
                raise ValueError(f"timeline {self.id} draws a route only where a cited text states the move")
        if [_dated(p) for p in self.points] != sorted(map(_dated, self.points)):
            raise ValueError(f"timeline {self.id} lists its points in time order")
        return self

    def cites_datasets(self) -> bool:
        return bool(self.datasets)

    def shown_labels(self) -> list[str]:
        return [place.name for place in self.places]


def _zoom_fields(level: str) -> set[str]:
    if level in IMAGE_ZOOM_LEVELS:
        return {"media", "relevance"}
    return {"district"} if level == "DISTRICT" else {"compound"}


def _level_label(level: ZoomLevel) -> str:
    if level.district is not None:
        return level.district.name
    if level.compound is not None:
        return level.compound.name
    return level.media.title if level.media is not None else level.level


def _require_stated_years(year_from: int, year_to: int, sentence: AnswerSentence) -> None:
    if (year_from, year_to) not in years_named(stated_texts(sentence)):
        raise ValueError(
            f"years {year_from} to {year_to} are not stated by sentence {sentence.id} or its quotes"
        )


def _version_problems(block: TimelineMapBlock) -> list[str]:
    registered = any(place.district_lgd is not None for place in block.places)
    if block.version == 1 and (block.undated or registered):
        return [f"timeline {block.id} lists undated sentences and register places from version 2"]
    return []


def _place_problems(
    block_id: str,
    places: list[TimelinePlace],
    points: list[TimelinePoint],
    routes: list[TimelineRoute],
    undated: list[TimelineUndated],
) -> list[str]:
    names = [place.name.casefold() for place in places]
    items = [wikidata for place in places if (wikidata := place.wikidata_id)]
    problems = []
    if len(set(names)) != len(names) or len(set(items)) != len(items):
        problems.append(f"timeline {block_id} lists each place once")
    used = [point.place for point in points] + [i for route in routes for i in (route.start, route.end)]
    used += [entry.place for entry in undated if entry.place is not None]
    if any(index >= len(places) for index in used):
        return [*problems, f"timeline {block_id} dates and joins only listed places"]
    if list(dict.fromkeys(used)) != list(range(len(places))):
        problems.append(f"timeline {block_id} lists its places in order of first use, each used")
    return problems


def _dated(point: TimelinePoint) -> tuple[int, int]:
    return point.year_from, point.year_to
