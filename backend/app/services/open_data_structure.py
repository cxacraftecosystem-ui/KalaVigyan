from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CraftGiRecord, CuratedCraft, ProcessStage

from .curated_index import (
    CuratedPage,
    IndexMaterial,
    IndexReaction,
    IndexStage,
    IndexTiming,
    IndexTool,
    stored_curated_page,
)
from .open_data_crafts import MERGED, CraftLookup
from .open_data_values import Row, published_ids

__all__ = ["CuratedStructure", "curated_structure"]


@dataclass(frozen=True)
class CuratedStructure:
    stages: list[Row]
    materials: list[Row]
    reactions: list[Row]
    native_names: list[Row]
    gi_records: list[Row]


@dataclass(frozen=True)
class _Page:
    craft: str
    page: CuratedPage
    shown: set[str]

    def cited(self, values: Iterable[uuid.UUID | None]) -> list[str]:
        return published_ids(values, self.shown)


async def curated_structure(session: AsyncSession, lookup: CraftLookup, shown: set[str]) -> CuratedStructure:
    pages = await _pages(session, lookup, shown)
    stage_ids = [stage.stage_id for found in pages for stage in found.page.stages]
    stages = await _stage_rows(session, stage_ids)
    return CuratedStructure(
        stages=_each(pages, lambda found: [_stage(found, stage, stages) for stage in found.page.stages]),
        materials=_each(pages, _materials),
        reactions=_each(
            pages, lambda found: [_reaction(found, reaction) for reaction in found.page.reactions]
        ),
        native_names=_each(pages, _native_names),
        gi_records=await _gi_rows(session, lookup, shown),
    )


async def _pages(session: AsyncSession, lookup: CraftLookup, shown: set[str]) -> list[_Page]:
    rows = (await session.scalars(select(CuratedCraft))).all()
    pages: list[_Page] = []
    for row in rows:
        craft = lookup.crafts.get(row.craftId)
        if craft is None or craft.status == MERGED:
            continue
        page = stored_curated_page(row.craftId, row.page)
        if page is not None:
            pages.append(_Page(craft=craft.slug, page=page, shown=shown))
    return sorted(pages, key=lambda found: found.craft)


async def _stage_rows(session: AsyncSession, stage_ids: list[uuid.UUID]) -> dict[uuid.UUID, ProcessStage]:
    if not stage_ids:
        return {}
    rows = await session.scalars(select(ProcessStage).where(ProcessStage.id.in_(stage_ids)))
    return {row.id: row for row in rows.all()}


def _each(pages: list[_Page], rows_of: Callable[[_Page], list[Row | None]]) -> list[Row]:
    return [row for found in pages for row in rows_of(found) if row is not None]


def _timing(found: _Page, timing: IndexTiming | None) -> str | None:
    if timing is None or not found.cited([timing.claim_id]):
        return None
    return timing.text


def _stage(found: _Page, stage: IndexStage, stored: Mapping[uuid.UUID, ProcessStage]) -> Row | None:
    row = stored.get(stage.stage_id)
    claims = found.cited(stage.claim_ids)
    after = stage.after if stage.after is not None and found.cited([stage.after.claim_id]) else None
    why = found.cited([stage.why_claim_id])
    if row is None or not (claims or after or why):
        return None
    return {
        "craft": found.craft,
        "key": stage.key,
        "order": stage.order,
        "name": row.name,
        "stage_type": row.stageType,
        "local_name": stage.local_name,
        "duration": _timing(found, stage.duration),
        "season": _timing(found, stage.season),
        "after": after.text if after is not None else None,
        "colours_after": list(after.colours) if after is not None else [],
        "why_claim_id": why[0] if why else None,
        "claim_ids": claims,
    }


def _materials(found: _Page) -> list[Row | None]:
    return [_material(found, item) for item in (*found.page.materials, *found.page.tools)]


def _material(found: _Page, item: IndexMaterial | IndexTool) -> Row | None:
    claims = found.cited(item.claim_ids)
    if not claims:
        return None
    material = item if isinstance(item, IndexMaterial) else None
    return {
        "craft": found.craft,
        "key": item.key,
        "name": item.name,
        "tool": material is None,
        "kind": material.kind if material is not None else None,
        "role": material.role if material is not None else None,
        "local_names": list(item.local_names),
        "botanical_name": material.botanical_name if material is not None else None,
        "pubchem_cid": material.pubchem_cid if material is not None else None,
        "claim_ids": claims,
    }


def _reaction(found: _Page, reaction: IndexReaction) -> Row | None:
    claims = found.cited(reaction.claim_ids)
    if not claims:
        return None
    return {
        "craft": found.craft,
        "key": reaction.key,
        "stage_key": reaction.stage_key,
        "kind": reaction.kind,
        "reactants": [{"name": s.name, "formula": s.formula} for s in reaction.reactants],
        "products": [{"name": s.name, "formula": s.formula} for s in reaction.products],
        "claim_ids": claims,
    }


def _native_names(found: _Page) -> list[Row | None]:
    named: dict[tuple[str, str], Row] = {}
    for name in found.page.native_names:
        if found.cited([name.claim_id]):
            row = {
                "craft": found.craft,
                "text": name.text,
                "language": name.language,
                "script": name.script,
                "claim_id": str(name.claim_id),
            }
            named.setdefault((row["claim_id"], name.text), row)
    return list(named.values())


async def _gi_rows(session: AsyncSession, lookup: CraftLookup, shown: set[str]) -> list[Row]:
    rows: list[Row] = []
    for record in (await session.scalars(select(CraftGiRecord))).all():
        craft = lookup.crafts.get(record.craftId)
        claims = published_ids(record.claimIds, shown)
        if craft is None or craft.status == MERGED or not claims:
            continue
        rows.append(
            {
                "craft": craft.slug,
                "application_number": record.applicationNumber,
                "certificate_number": record.certificateNumber,
                "filed_on": record.filedOn,
                "registered_on": record.registeredOn,
                "journal_issue": record.journalIssue,
                "proprietors": list(record.proprietors or []),
                "authorised_users": record.authorisedUserCount,
                "claim_ids": claims,
            }
        )
    return sorted(rows, key=lambda row: row["craft"])
