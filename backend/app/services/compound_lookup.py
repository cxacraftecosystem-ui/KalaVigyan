from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ExternalFailure, InvalidInput
from app.data.craft_master_loader import ID_NAMESPACE
from app.models import Compound, Source
from app.science.formula import hill_formula, parse_formula
from app.sources.reference.pubchem import PUBCHEM_LICENCE, PUBCHEM_PUBLISHER, PubChemAdapter, PubChemCompound
from app.sources.reference.registry import reference_sources

__all__ = [
    "CANDIDATES",
    "CompoundFinder",
    "LinkReport",
    "find_compound",
    "link_compounds",
    "pubchem_finder",
    "record_source_id",
]

logger = logging.getLogger(__name__)

CANDIDATES = 3


class CompoundFinder(Protocol):
    async def compounds(self, text: str, k: int) -> list[PubChemCompound]: ...

    async def compound(self, cid: int) -> PubChemCompound | None: ...


@dataclass
class LinkReport:
    linked: list[str] = field(default_factory=list)
    not_found: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    filled: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "linked": self.linked,
            "filled": self.filled,
            "notFound": self.not_found,
            "failed": self.failed,
            "ok": not self.failed,
        }


@dataclass(frozen=True)
class _StoredCompound:
    id: uuid.UUID
    name: str
    formula: str | None
    pubchem_cid: int | None
    source_id: uuid.UUID | None

    def pending_formula(self) -> str | None:
        return self.formula if self.pubchem_cid is None else None

    def unfilled_cid(self) -> int | None:
        if self.formula is not None and self.source_id is not None:
            return None
        return self.pubchem_cid

    def unchanged_in(self, row: Compound) -> bool:
        return (row.pubchemCid, row.formula, row.sourceId) == (self.pubchem_cid, self.formula, self.source_id)


@dataclass(frozen=True)
class _FoundRecord:
    compound: _StoredCompound
    record: PubChemCompound


def pubchem_finder(client: httpx.AsyncClient) -> PubChemAdapter:
    return next(adapter for adapter in reference_sources(client) if isinstance(adapter, PubChemAdapter))


async def find_compound(finder: CompoundFinder, *, name: str, formula: str) -> PubChemCompound | None:
    wanted = parse_formula(formula)
    if not wanted.neutral:
        raise InvalidInput(f"{formula} is an ion; only neutral compounds are looked up")
    for query in (name, hill_formula(wanted)):
        for candidate in await finder.compounds(query, CANDIDATES):
            if _same_composition(candidate, dict(wanted.counts)):
                return candidate
    return None


async def link_compounds(
    sessions: async_sessionmaker[AsyncSession], finder: CompoundFinder, *, now: datetime
) -> LinkReport:
    async with sessions() as session:
        stored = await _stored_compounds(session)
    report = LinkReport()
    links = await _look_up_pending(finder, stored, report)
    fills = await _look_up_unfilled(finder, stored, report)
    if links or fills:
        async with sessions() as session:
            report.linked.extend(await _written(session, links, now=now))
            report.filled.extend(await _written(session, fills, now=now))
            await session.commit()
    return report


async def _stored_compounds(session: AsyncSession) -> list[_StoredCompound]:
    rows = await session.execute(
        select(Compound.id, Compound.name, Compound.formula, Compound.pubchemCid, Compound.sourceId)
        .where(or_(Compound.pubchemCid.is_not(None), Compound.formula.is_not(None)))
        .order_by(Compound.name, Compound.id)
    )
    return [_StoredCompound(*row) for row in rows.all()]


async def _look_up_pending(
    finder: CompoundFinder, stored: Sequence[_StoredCompound], report: LinkReport
) -> list[_FoundRecord]:
    taken = {compound.pubchem_cid for compound in stored if compound.pubchem_cid is not None}
    links: list[_FoundRecord] = []
    for compound in stored:
        formula = compound.pending_formula()
        if formula is None:
            continue
        try:
            found = await find_compound(finder, name=compound.name, formula=formula)
        except ExternalFailure as failure:
            logger.warning("compound lookup failed for %s: %s", compound.name, failure)
            report.failed.append(compound.name)
            continue
        if found is None or found.cid in taken:
            report.not_found.append(compound.name)
            continue
        taken.add(found.cid)
        links.append(_FoundRecord(compound, found))
    return links


async def _look_up_unfilled(
    finder: CompoundFinder, stored: Sequence[_StoredCompound], report: LinkReport
) -> list[_FoundRecord]:
    fills: list[_FoundRecord] = []
    for compound in stored:
        cid = compound.unfilled_cid()
        if cid is None:
            continue
        try:
            found = await finder.compound(cid)
        except ExternalFailure as failure:
            logger.warning("compound record lookup failed for %s: %s", compound.name, failure)
            report.failed.append(compound.name)
            continue
        if found is None or found.cid != cid or not _record_of(compound.formula, found):
            report.not_found.append(compound.name)
            continue
        fills.append(_FoundRecord(compound, found))
    return fills


async def _written(session: AsyncSession, found: Sequence[_FoundRecord], *, now: datetime) -> list[str]:
    written: list[str] = []
    for each in found:
        row = await session.get(Compound, each.compound.id, with_for_update=True)
        if row is None or not each.compound.unchanged_in(row) or await _held_elsewhere(session, each):
            logger.warning(
                "compound %s changed while PubChem was asked; it is left for the next run", each.compound.name
            )
            continue
        row.formula = row.formula or each.record.formula
        _fill(row, each.record, await _record_source(session, each.record, now))
        written.append(each.compound.name)
    return written


async def _held_elsewhere(session: AsyncSession, found: _FoundRecord) -> bool:
    holder = await session.scalar(
        select(Compound.id)
        .where(Compound.pubchemCid == found.record.cid, Compound.id != found.compound.id)
        .limit(1)
    )
    return holder is not None


def _record_of(formula: str | None, found: PubChemCompound) -> bool:
    if not found.formula:
        return False
    if not formula:
        return True
    try:
        return _same_composition(found, dict(parse_formula(formula).counts))
    except InvalidInput:
        return False


def _same_composition(candidate: PubChemCompound, counts: dict[str, int]) -> bool:
    if not candidate.formula:
        return False
    try:
        found = parse_formula(candidate.formula)
    except InvalidInput:
        return False
    return found.neutral and dict(found.counts) == counts


def record_source_id(cid: int) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"pubchem-record:{cid}")


async def _record_source(session: AsyncSession, found: PubChemCompound, now: datetime) -> Source:
    existing = (await session.scalars(select(Source).where(Source.url == found.url))).first()
    if existing is not None:
        return existing
    source = Source(
        id=record_source_id(found.cid),
        kind="COMPOUND_RECORD",
        title=f"{found.title} (PubChem CID {found.cid})",
        authors=[],
        url=found.url,
        publisher=PUBCHEM_PUBLISHER,
        licence=PUBCHEM_LICENCE,
        attribution=f"PubChem, {PUBCHEM_PUBLISHER}, CID {found.cid}",
        reliability="A",
        storage="LINK_ONLY",
        retrievedAt=now,
        origin="ENRICHMENT",
        externalIds={"pubchem_cid": str(found.cid)},
    )
    session.add(source)
    await session.flush()
    return source


def _fill(compound: Compound, found: PubChemCompound, source: Source) -> None:
    compound.pubchemCid = found.cid
    compound.iupacName = found.iupac_name
    compound.smiles = found.smiles
    compound.inchiKey = found.inchikey
    compound.molecularWeight = _weight(found.molecular_weight)
    compound.sourceId = source.id


def _weight(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise InvalidInput(f"PubChem molecular weight {value!r} is not a number") from error
