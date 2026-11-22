from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def link_compounds(session: AsyncSession, finder: CompoundFinder, *, now: datetime) -> LinkReport:
    report = LinkReport()
    pending = (
        await session.scalars(
            select(Compound)
            .where(Compound.pubchemCid.is_(None), Compound.formula.is_not(None))
            .order_by(Compound.name)
        )
    ).all()
    taken = set(
        (await session.scalars(select(Compound.pubchemCid).where(Compound.pubchemCid.is_not(None)))).all()
    )
    for compound in pending:
        try:
            found = await find_compound(finder, name=compound.name, formula=str(compound.formula))
        except ExternalFailure as failure:
            logger.warning("compound lookup failed for %s: %s", compound.name, failure)
            report.failed.append(compound.name)
            continue
        if found is None or found.cid in taken:
            report.not_found.append(compound.name)
            continue
        taken.add(found.cid)
        _fill(compound, found, await _record_source(session, found, now))
        report.linked.append(compound.name)
    await _fill_known_records(session, finder, report, now=now)
    await session.flush()
    return report


async def _fill_known_records(
    session: AsyncSession, finder: CompoundFinder, report: LinkReport, *, now: datetime
) -> None:
    unfilled = (
        await session.scalars(
            select(Compound)
            .where(
                Compound.pubchemCid.is_not(None), or_(Compound.formula.is_(None), Compound.sourceId.is_(None))
            )
            .order_by(Compound.name)
        )
    ).all()
    for compound in unfilled:
        try:
            found = await finder.compound(int(compound.pubchemCid or 0))
        except ExternalFailure as failure:
            logger.warning("compound record lookup failed for %s: %s", compound.name, failure)
            report.failed.append(compound.name)
            continue
        if found is None or found.cid != compound.pubchemCid or not _record_of(compound, found):
            report.not_found.append(compound.name)
            continue
        compound.formula = compound.formula or found.formula
        _fill(compound, found, await _record_source(session, found, now))
        report.filled.append(compound.name)


def _record_of(compound: Compound, found: PubChemCompound) -> bool:
    if not found.formula:
        return False
    if not compound.formula:
        return True
    try:
        return _same_composition(found, dict(parse_formula(compound.formula).counts))
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
