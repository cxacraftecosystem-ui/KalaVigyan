from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass

from app.composer.material_cards import choose_card_statements
from app.research.blocks_matter import Molecule3dBlock
from app.research.explainer import Block
from app.science.reaction_player import reaction_player, reaction_player_problems
from app.science.records import CompoundRecord

from .builder_evidence import sources_beyond
from .builder_interface import BuildAsk, BuilderTools, Built, SourceRefs
from .craft_matter import CraftMatter, MaterialRows, first_naming, section_sentences
from .material_cards import card_offers, material_card
from .molecule_conformers import ConformerCache, ConformerObjects, ConformerSource, live_pubchem
from .object_store import media_bucket

__all__ = [
    "MATERIAL_CARD_WAIT_SECONDS",
    "MOLECULES_PER_SECTION",
    "MOLECULE_CANDIDATES_MAX",
    "PLAYED_FIELDS",
    "LinkedCompound",
    "MaterialCardBuilder",
    "MoleculeBuilder",
    "ReactionPlayerBuilder",
    "molecule_candidates",
    "played_compounds",
]

logger = logging.getLogger(__name__)

MATERIAL_CARD_WAIT_SECONDS = 20.0
MOLECULE_CANDIDATES_MAX = 6
MOLECULES_PER_SECTION = 3
PLAYED_FIELDS = frozenset({"CHEMISTRY"})

Bucket = Callable[[], ConformerObjects | None]
PubChem = Callable[[], Awaitable[ConformerSource]]


class ReactionPlayerBuilder:
    def __init__(self, tools: BuilderTools) -> None:
        self._tools = tools

    async def build(self, ask: BuildAsk) -> Built:
        matter = await _matter(self._tools, ask)
        if matter is None:
            return Built()
        cited = {claim for block in ask.blocks for claim in block.cited_claim_ids()}
        block = reaction_player(matter.records, block_id=f"{ask.section.id}.reactions", cited_claim_ids=cited)
        if block is None:
            return Built()
        problems = reaction_player_problems(block, matter.records)
        if problems:
            logger.warning("reaction player of section %s refused: %s", ask.section.id, "; ".join(problems))
            return Built()
        return Built((block,), sources_beyond([block], matter.records.sources, ask.cited))


class MaterialCardBuilder:
    def __init__(self, tools: BuilderTools) -> None:
        self._tools = tools

    async def build(self, ask: BuildAsk) -> Built:
        matter = await _matter(self._tools, ask)
        if matter is None:
            return Built()
        offers = card_offers(matter, ask.blocks, ask.cited)
        if not offers:
            return Built()
        choices = await choose_card_statements(self._tools.plan_model, [offer.brief() for offer in offers])
        by_ref = {offer.ref: offer for offer in offers}
        cards: list[Block] = []
        for choice in choices:
            offer = by_ref.pop(choice.material, None)
            card = (
                None
                if offer is None
                else material_card(
                    offer, choice, block_id=_card_id(ask, len(cards)), records=matter.record_sources
                )
            )
            if card is not None:
                cards.append(card)
        return Built(
            tuple(cards),
            {**sources_beyond(cards, matter.records.sources, ask.cited), **_records(cards, matter)},
        )


class MoleculeBuilder:
    def __init__(
        self, tools: BuilderTools, *, bucket: Bucket | None = None, pubchem: PubChem | None = None
    ) -> None:
        self._tools = tools
        self._bucket = bucket or media_bucket
        self._pubchem = pubchem or (lambda: live_pubchem(tools.live, tools.sessions))

    async def build(self, ask: BuildAsk) -> Built:
        objects = self._bucket()
        if objects is None:
            return Built()
        matter = await _matter(self._tools, ask)
        if matter is None:
            return Built()
        played = played_compounds(matter) if ask.section.discipline in PLAYED_FIELDS else []
        candidates = _distinct([*molecule_candidates(matter, ask.blocks), *played])[:MOLECULE_CANDIDATES_MAX]
        if not candidates:
            return Built()
        cache = ConformerCache(objects=objects, source=await self._pubchem())
        drawn: list[LinkedCompound] = []
        for candidate in candidates:
            if len(drawn) == MOLECULES_PER_SECTION:
                break
            if await cache.conformer(candidate.pubchem_cid) is not None:
                drawn.append(candidate)
        return _molecules(ask, drawn, matter)


@dataclass(frozen=True)
class LinkedCompound:
    compound: CompoundRecord
    pubchem_cid: int
    source_id: str


def molecule_candidates(matter: CraftMatter, blocks: Sequence[Block]) -> list[LinkedCompound]:
    sentences = section_sentences(blocks)
    named: list[tuple[int, LinkedCompound]] = []
    for compound in matter.compounds.values():
        source_id = str(compound.source_id)
        if compound.pubchem_cid is None or source_id not in matter.record_sources:
            continue
        position = first_naming(sentences, _compound_surfaces(compound, matter), _term_keys(compound, matter))
        if position is not None:
            named.append((position, LinkedCompound(compound, compound.pubchem_cid, source_id)))
    return _distinct(
        [linked for _, linked in sorted(named, key=lambda pair: (pair[0], pair[1].compound.name))]
    )


def played_compounds(matter: CraftMatter) -> list[LinkedCompound]:
    ids = dict.fromkeys(s.compound_id for r in matter.records.reactions for s in r.species if s.compound_id)
    found = [matter.compounds[compound_id] for compound_id in ids if compound_id in matter.compounds]
    return [
        LinkedCompound(compound, compound.pubchem_cid, str(compound.source_id))
        for compound in found
        if compound.pubchem_cid is not None and str(compound.source_id) in matter.record_sources
    ]


def _distinct(linked: Sequence[LinkedCompound]) -> list[LinkedCompound]:
    first: dict[int, LinkedCompound] = {}
    for candidate in linked:
        first.setdefault(candidate.pubchem_cid, candidate)
    return list(first.values())


async def _matter(tools: BuilderTools, ask: BuildAsk) -> CraftMatter | None:
    if ask.request.craft is None:
        return None
    return await ask.matter.read(tools.sessions, ask.request.craft)


def _molecules(ask: BuildAsk, drawn: Sequence[LinkedCompound], matter: CraftMatter) -> Built:
    blocks = tuple(
        Molecule3dBlock(
            id=f"{ask.section.id}.molecule{number}",
            kind="molecule_3d",
            version=1,
            reuse=None,
            compound_id=linked.compound.id,
            pubchem_cid=linked.pubchem_cid,
            name=linked.compound.name,
            formula=linked.compound.formula,
            source_id=linked.source_id,
        )
        for number, linked in enumerate(drawn, start=1)
    )
    return Built(blocks, _records(blocks, matter))


def _records(blocks: Sequence[Block], matter: CraftMatter) -> SourceRefs:
    return {
        source_id: matter.record_sources[source_id]
        for block in blocks
        for source_id in block.direct_source_ids()
        if source_id in matter.record_sources
    }


def _compound_surfaces(compound: CompoundRecord, matter: CraftMatter) -> list[str]:
    surfaces = [compound.name]
    surfaces += [
        s.name for r in matter.records.reactions for s in r.species if s.compound_id == compound.id and s.name
    ]
    for material in _materials_of(compound, matter):
        surfaces += material.surfaces()
    return surfaces


def _term_keys(compound: CompoundRecord, matter: CraftMatter) -> Iterable[str]:
    return [term.key for material in _materials_of(compound, matter) for term in material.terms]


def _materials_of(compound: CompoundRecord, matter: CraftMatter) -> list[MaterialRows]:
    return [m for m in matter.materials if m.compound is not None and m.compound.id == compound.id]


def _card_id(ask: BuildAsk, made: int) -> str:
    return f"{ask.section.id}.card{made + 1}"
