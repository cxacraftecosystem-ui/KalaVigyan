from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure, InvalidInput, NotConfigured
from app.sources.reference.pubchem import PubChemAdapter

from .compose_dip import dip_player
from .compose_held import About, Composition, CraftHeld, HeldFact, refused
from .compose_lab import experiment_lab
from .compose_molecule import molecule_3d, molecule_candidates
from .compose_named import CompoundRecords, Naming, fact_named_compound, held_by_material, page_facts
from .compose_reaction import reaction_player
from .compose_reads import craft_held
from .molecule_conformers import ConformerCache
from .object_store import media_bucket
from .source_lookup_store import lookup_sources

__all__ = [
    "COMPOSED_KINDS",
    "ComposeDeps",
    "ConformerReader",
    "compose_component",
    "compose_every_kind",
    "stored_conformers",
    "stored_records",
]

logger = logging.getLogger(__name__)

COMPOSED_KINDS = ("reaction_player", "dip_player", "molecule_3d", "experiment_lab")
REACTION_PLAYER, DIP_PLAYER, MOLECULE_3D, EXPERIMENT_LAB = COMPOSED_KINDS
NO_PAGE = (
    "a curated page for {slug}: it holds no stages, materials or reactions yet; propose its facts with "
    "propose_facts and its structure with propose_structure first"
)
UNREACHED = "PubChem's 3D conformer of CID {cid}, which could not be read just now; compose it again later"
NO_BUCKET = "The media store is not set up on this server, so no 3D conformer can be kept or read."
NO_PUBCHEM = "PubChem is not among this server's sources just now, so no 3D conformer can be read."


class ConformerReader(Protocol):
    async def conformer(self, cid: int) -> str | None: ...


async def stored_conformers() -> ConformerReader:
    objects = media_bucket()
    if objects is None:
        raise NotConfigured("media", NO_BUCKET)
    pubchem = (await lookup_sources()).compounds
    if not isinstance(pubchem, PubChemAdapter):
        raise NotConfigured("pubchem", NO_PUBCHEM)
    return ConformerCache(objects=objects, source=pubchem)


async def stored_records() -> CompoundRecords:
    pubchem = (await lookup_sources()).compounds
    if pubchem is None:
        raise NotConfigured("pubchem", NO_PUBCHEM)
    return pubchem


HeldReader = Callable[[AsyncSession, str], Awaitable[CraftHeld | None]]
ConformerOpener = Callable[[], Awaitable[ConformerReader]]
RecordOpener = Callable[[], Awaitable[CompoundRecords]]
FactsReader = Callable[[AsyncSession, str], Awaitable[Mapping[uuid.UUID, HeldFact]]]
Composer = Callable[[CraftHeld, About], Composition]
COMPOSERS: Mapping[str, Composer] = MappingProxyType(
    {REACTION_PLAYER: reaction_player, DIP_PLAYER: dip_player, EXPERIMENT_LAB: experiment_lab}
)


@dataclass(frozen=True)
class ComposeDeps:
    held: HeldReader = craft_held
    conformers: ConformerOpener = stored_conformers
    records: RecordOpener = stored_records
    facts: FactsReader = page_facts


async def compose_component(
    session: AsyncSession, deps: ComposeDeps, craft_slug: str, kind: str, about: About
) -> Composition:
    held = await deps.held(session, craft_slug)
    if held is None:
        return refused(NO_PAGE.format(slug=craft_slug))
    return await _composed(session, held, kind, about, deps)


async def compose_every_kind(
    session: AsyncSession, deps: ComposeDeps, craft_slug: str
) -> dict[str, Composition]:
    held = await deps.held(session, craft_slug)
    if held is None:
        return dict.fromkeys(COMPOSED_KINDS, refused(NO_PAGE.format(slug=craft_slug)))
    return {kind: await _settled(session, held, kind, deps) for kind in COMPOSED_KINDS}


async def _composed(
    session: AsyncSession, held: CraftHeld, kind: str, about: About, deps: ComposeDeps
) -> Composition:
    if kind == MOLECULE_3D:
        return await _molecules(session, held, about, deps)
    return COMPOSERS[kind](held, about)


async def _settled(session: AsyncSession, held: CraftHeld, kind: str, deps: ComposeDeps) -> Composition:
    try:
        return await _composed(session, held, kind, About(), deps)
    except NotConfigured as missing:
        return refused(missing.message)
    except InvalidInput as unstated:
        return refused(str(unstated))


async def _molecules(session: AsyncSession, held: CraftHeld, about: About, deps: ComposeDeps) -> Composition:
    naming = await _named(session, held, about, deps)
    if naming.problem is not None:
        return refused(naming.problem)
    candidates, problem = molecule_candidates(naming.craft, about, naming.compounds)
    if problem is not None:
        return refused(problem)
    cids = [candidate.compound.cid for candidate in candidates]
    found, gaps = await _conformers(await deps.conformers(), cids)
    return _with_gaps(molecule_3d(naming.craft, about, found, naming.compounds), gaps)


async def _named(session: AsyncSession, held: CraftHeld, about: About, deps: ComposeDeps) -> Naming:
    cid = about.compound
    if cid is None or held_by_material(held, cid):
        return Naming(held)
    return await fact_named_compound(held, cid, await deps.records(), await deps.facts(session, held.slug))


async def _conformers(
    reader: ConformerReader, cids: Sequence[int]
) -> tuple[dict[int, str | None], list[str]]:
    found: dict[int, str | None] = {}
    gaps: list[str] = []
    for cid in dict.fromkeys(cids):
        try:
            found[cid] = await reader.conformer(cid)
        except ExternalFailure as failure:
            logger.warning(
                "the 3D conformer of CID %s could not be read to compose a model: %s", cid, failure
            )
            gaps.append(UNREACHED.format(cid=cid))
    return found, gaps


def _with_gaps(result: Composition, gaps: Sequence[str]) -> Composition:
    if not gaps:
        return result
    if result.composed:
        return replace(result, left_out=(*result.left_out, *gaps))
    return refused(*result.missing, *gaps)
