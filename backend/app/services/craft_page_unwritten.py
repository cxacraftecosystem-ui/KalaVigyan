from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source
from app.models.enums import DISCIPLINES
from app.research.coverage_chapters import field_chapter
from app.research.vocabulary import LEVEL_ORDER

from . import knowledge_view
from .knowledge_view import ClaimView
from .monograph_generated_parts import FIELD_ORDER, StoredSection
from .monograph_generated_units import DraftUnit
from .open_work_counts import Owners, owned_facts
from .open_work_subjects import CATEGORY, WorkSubject

__all__ = [
    "FACT_TAG",
    "UNWRITTEN_PER_FIELD",
    "UnwrittenFacts",
    "listed_units",
    "unwritten_facts",
    "unwritten_units",
    "with_listed_fields",
]

UNWRITTEN_PER_FIELD = 12
LISTED_VERSION = 0
FACT_TAG = "li"
FACT_UNIT_PREFIX = "fact-"
FACT_UNIT_DIGITS = 12


@dataclass(frozen=True)
class UnwrittenFacts:
    by_field: Mapping[str, tuple[ClaimView, ...]] = field(default_factory=dict)
    sources: Mapping[uuid.UUID, Source] = field(default_factory=dict)

    def views(self) -> dict[uuid.UUID, ClaimView]:
        return {view.id: view for found in self.by_field.values() for view in found}


async def unwritten_facts(
    session: AsyncSession, subject: WorkSubject, shown: Iterable[uuid.UUID]
) -> UnwrittenFacts:
    cited = set(shown)
    filed = await _filed(session, subject)
    wanted = [claim_id for claim_id in filed if claim_id not in cited]
    views, sources = await knowledge_view.claims_by_id(session, wanted)
    by_field: dict[str, list[ClaimView]] = {}
    for claim_id in wanted:
        if claim_id in views:
            by_field.setdefault(filed[claim_id], []).append(views[claim_id])
    ordered = {
        discipline: tuple(_ordered(by_field[discipline])[:UNWRITTEN_PER_FIELD])
        for discipline in DISCIPLINES
        if discipline in by_field
    }
    kept = {cite["sourceId"] for found in ordered.values() for view in found for cite in view.citations}
    return UnwrittenFacts(
        by_field=ordered,
        sources={source_id: row for source_id, row in sources.items() if str(source_id) in kept},
    )


async def _filed(session: AsyncSession, subject: WorkSubject) -> dict[uuid.UUID, str]:
    owners = (
        Owners(crafts=(), categories=(subject.id,))
        if subject.kind == CATEGORY
        else Owners(crafts=(subject.id,), categories=())
    )
    owned = owned_facts(owners)
    rows = await session.execute(select(owned.c.claim, owned.c.field).where(owned.c.field.is_not(None)))
    return dict(rows.tuples().all())


def with_listed_fields(
    sections: Sequence[StoredSection], unwritten: Mapping[str, Sequence[ClaimView]]
) -> list[StoredSection]:
    written = {section.field for section in sections}
    listed = [StoredSection(found, LISTED_VERSION, ()) for found in unwritten if found not in written]
    return sorted([*sections, *listed], key=lambda section: FIELD_ORDER.get(section.field, len(FIELD_ORDER)))


def listed_units(
    field_name: str,
    unwritten: Mapping[str, Sequence[ClaimView]],
    drafts: dict[str, DraftUnit],
    taken: set[str],
) -> list[str]:
    units = unwritten_units(field_name, unwritten.get(field_name, ()), taken)
    drafts.update((unit.unit_id, unit) for unit in units)
    return [unit.unit_id for unit in units]


def unwritten_units(field_name: str, views: Sequence[ClaimView], taken: set[str]) -> list[DraftUnit]:
    units = []
    for view in views:
        unit_id = f"{FACT_UNIT_PREFIX}{field_name.lower()}-{view.id.hex[:FACT_UNIT_DIGITS]}"
        if unit_id in taken:
            continue
        taken.add(unit_id)
        units.append(
            DraftUnit(unit_id, field_chapter(field_name), field_name, view.text, (view.id,), tag=FACT_TAG)
        )
    return units


def _ordered(views: Sequence[ClaimView]) -> list[ClaimView]:
    return sorted(views, key=lambda view: (LEVEL_ORDER.get(view.level, len(LEVEL_ORDER)), view.text))
