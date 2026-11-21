from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Self

from pydantic import Field, model_validator

from .base import ContractModel
from .blocks_people import ExpertSeat
from .depth import depth_policy
from .vocabulary import Discipline, SourceType

__all__ = [
    "EXPERT_PANEL",
    "PANEL_FIELDS",
    "SEAT_BRIEF_MAX_CHARS",
    "TESTIMONY_SEATS",
    "WIDENED_DEPTHS",
    "SeatBrief",
    "panel_seats",
    "seats_for",
    "speaking_seats",
    "voiced_seats",
]

SEAT_BRIEF_MAX_CHARS = 400
TESTIMONY_SEATS = frozenset({"ARTISAN"})
WIDENED_DEPTHS = frozenset({"EXPERT"})


class SeatBrief(ContractModel):
    seat: ExpertSeat
    label: str = Field(min_length=1, max_length=60)
    brief: str = Field(min_length=1, max_length=SEAT_BRIEF_MAX_CHARS)
    source_kinds: tuple[SourceType, ...] = Field(min_length=1)
    fields: tuple[Discipline, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _each_kind_and_field_once(self) -> Self:
        if len(set(self.source_kinds)) != len(self.source_kinds) or len(set(self.fields)) != len(self.fields):
            raise ValueError(f"seat {self.seat} lists each source kind and field once")
        return self


def _seat(
    seat: str, label: str, brief: str, source_kinds: Sequence[str], fields: Sequence[str]
) -> tuple[str, SeatBrief]:
    return seat, SeatBrief(
        seat=seat, label=label, brief=brief, source_kinds=tuple(source_kinds), fields=tuple(fields)
    )


EXPERT_PANEL: Mapping[str, SeatBrief] = MappingProxyType(
    dict(
        [
            _seat(
                "CHEMIST",
                "Chemist",
                "Explains the reactions, compounds and conditions behind each step: what binds, "
                "oxidises, reduces or dissolves, and why the colour or finish follows.",
                (
                    "PAPER",
                    "BOOK",
                    "COMPOUND_RECORD",
                    "ENCYCLOPEDIA",
                    "BOOK_CHAPTER",
                    "GI_JOURNAL",
                    "WEB_PAGE",
                ),
                ("CHEMISTRY", "PROCESS", "MATERIALS", "HEALTH"),
            ),
            _seat(
                "PHYSICIST",
                "Physicist",
                "Explains heat, light, drying, flow and the mechanics of tools as the sources describe them.",
                ("PAPER", "BOOK", "ENCYCLOPEDIA", "BOOK_CHAPTER", "GI_JOURNAL", "WEB_PAGE"),
                ("PHYSICS", "PROCESS", "MATERIALS"),
            ),
            _seat(
                "MATERIALS_SCIENTIST",
                "Materials scientist",
                "Explains how fibres, clays, metals and pigments are built and why that structure gives "
                "the properties the craft relies on.",
                ("PAPER", "BOOK", "COMPOUND_RECORD", "BOOK_CHAPTER", "GI_JOURNAL", "WEB_PAGE", "OTHER"),
                ("MATERIALS", "CHEMISTRY", "PHYSICS", "PROCESS"),
            ),
            _seat(
                "TECHNOLOGIST",
                "Textile or ceramic technologist",
                "Explains process control, quality, standards and yields: what a workshop measures, "
                "adjusts and checks.",
                ("PAPER", "GOVERNMENT_REPORT", "GI_JOURNAL", "BOOK", "BOOK_CHAPTER", "WEB_PAGE", "OTHER"),
                ("PROCESS", "MATERIALS", "ECONOMICS"),
            ),
            _seat(
                "GEOLOGIST",
                "Geologist",
                "Explains the rocks, minerals and clays of the region and how the ground supplies the craft.",
                ("DATASET", "PAPER", "GOVERNMENT_REPORT", "BOOK_CHAPTER", "WEB_PAGE"),
                ("GEOLOGY", "GEOGRAPHY", "MATERIALS"),
            ),
            _seat(
                "HYDROLOGIST",
                "Hydrologist",
                "Explains rivers, groundwater and water quality: where the water comes from, where it "
                "goes and what it carries.",
                ("DATASET", "GOVERNMENT_REPORT", "PAPER", "BOOK_CHAPTER", "OTHER"),
                ("GEOGRAPHY", "CLIMATE", "PROCESS"),
            ),
            _seat(
                "SOIL_SCIENTIST",
                "Soil scientist",
                "Explains soils, salinity and fertility where fibre and dye plants grow.",
                ("DATASET", "PAPER", "BOOK_CHAPTER"),
                ("GEOLOGY", "BOTANY", "ECOLOGY"),
            ),
            _seat(
                "CLIMATOLOGIST",
                "Climatologist",
                "Explains rainfall, temperature, humidity and seasons, and how they shape the craft's year.",
                ("DATASET", "PAPER", "GOVERNMENT_REPORT", "BOOK_CHAPTER"),
                ("CLIMATE", "GEOGRAPHY"),
            ),
            _seat(
                "ECOLOGIST",
                "Ecologist",
                "Explains the living systems around the craft: effluent, habitats and what the work takes "
                "from and returns to them.",
                ("PAPER", "GOVERNMENT_REPORT", "DATASET", "BOOK_CHAPTER", "OTHER"),
                ("ECOLOGY", "GEOGRAPHY", "HEALTH"),
            ),
            _seat(
                "BOTANIST",
                "Botanist",
                "Explains the dye and fibre plants: which parts are used, where they grow and what they hold.",
                ("PAPER", "BOOK", "ENCYCLOPEDIA", "BOOK_CHAPTER", "WEB_PAGE"),
                ("BOTANY", "MATERIALS", "ECOLOGY"),
            ),
            _seat(
                "TOXICOLOGIST",
                "Toxicologist",
                "Explains exposure, hazards and safe handling of the materials, from cited hazard records.",
                ("COMPOUND_RECORD", "PAPER", "GOVERNMENT_REPORT", "BOOK_CHAPTER"),
                ("HEALTH", "CHEMISTRY"),
            ),
            _seat(
                "HISTORIAN",
                "Historian",
                "Explains origins, dates, migrations and trade from documents and dated objects.",
                ("BOOK", "PAPER", "GI_JOURNAL", "ENCYCLOPEDIA", "BOOK_CHAPTER", "WEB_PAGE", "OTHER"),
                ("HISTORY", "OVERVIEW"),
            ),
            _seat(
                "ANTHROPOLOGIST",
                "Anthropologist",
                "Explains the communities who make and use the craft, their practice and what it means to them.",
                ("FIELD_TESTIMONY", "PAPER", "BOOK", "WEB_PAGE", "BOOK_CHAPTER", "OTHER"),
                ("SOCIETY", "HISTORY", "OVERVIEW", "DESIGN", "ECONOMICS"),
            ),
            _seat(
                "ECONOMIST",
                "Economist",
                "Explains markets, prices, livelihoods and the costs of making, with their date and place.",
                ("GOVERNMENT_REPORT", "PAPER", "DATASET", "BOOK_CHAPTER", "WEB_PAGE", "OTHER"),
                ("ECONOMICS", "SOCIETY", "POLICY"),
            ),
            _seat(
                "DESIGN_HISTORIAN",
                "Design and art historian",
                "Explains motifs, styles and their lineage, from museum objects and design literature.",
                ("BOOK", "PAPER", "WEB_PAGE", "BOOK_CHAPTER", "OTHER"),
                ("DESIGN", "HISTORY"),
            ),
            _seat(
                "CONSERVATOR",
                "Conservator",
                "Explains how finished pieces age, fade and are cared for, from conservation studies.",
                ("PAPER", "BOOK", "WEB_PAGE", "BOOK_CHAPTER", "OTHER"),
                ("MATERIALS", "CHEMISTRY", "DESIGN"),
            ),
            _seat(
                "POLICY_EXPERT",
                "GI and policy expert",
                "Explains Geographical Indication registration, standards and public schemes for the craft.",
                ("GI_JOURNAL", "GOVERNMENT_REPORT", "WEB_PAGE", "OTHER"),
                ("POLICY", "ECONOMICS", "HISTORY", "OVERVIEW"),
            ),
            _seat(
                "ARTISAN",
                "Artisan's voice",
                "Gives the makers' own account of the work, quoted from their recorded words.",
                ("FIELD_TESTIMONY", "WEB_PAGE"),
                ("PROCESS", "DESIGN", "OVERVIEW", "HISTORY"),
            ),
        ]
    )
)


PANEL_FIELDS = frozenset(
    field for seat, brief in EXPERT_PANEL.items() if seat not in TESTIMONY_SEATS for field in brief.fields
)


def seats_for(discipline: str, seated: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        seat
        for seat in dict.fromkeys(seated)
        if seat in EXPERT_PANEL and discipline in EXPERT_PANEL[seat].fields
    )


def panel_seats(discipline: str | None, seated: Sequence[str], *, depth: str | None) -> tuple[str, ...]:
    if discipline is None:
        return ()
    panel = tuple(seat for seat in dict.fromkeys(seated) if seat in EXPERT_PANEL)
    if depth is None:
        return seats_for(discipline, panel)
    limit = depth_policy(depth).max_experts
    if depth not in WIDENED_DEPTHS:
        return seats_for(discipline, panel[:limit])
    return seats_for(discipline, (*panel, *EXPERT_PANEL))[:limit]


def speaking_seats(discipline: str | None, seated: Sequence[str], *, depth: str | None) -> tuple[str, ...]:
    return tuple(seat for seat in panel_seats(discipline, seated, depth=depth) if seat not in TESTIMONY_SEATS)


def voiced_seats(discipline: str | None, seated: Sequence[str], *, depth: str | None) -> tuple[str, ...]:
    return tuple(seat for seat in panel_seats(discipline, seated, depth=depth) if seat in TESTIMONY_SEATS)
