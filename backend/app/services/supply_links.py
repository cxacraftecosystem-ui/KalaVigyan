from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from app.composer.supply_map import NO_MATERIAL, SupplyBrief, SupplyItem, SupplyLinkChoice
from app.research.blocks import ExplainerSentence
from app.research.blocks_place import SupplyLink, SupplyMapBlock
from app.research.datasets import DatasetRef
from app.research.explainer import Block
from app.research.vocabulary import FACT_LEVELS
from app.science.records import KnownClaim

from .answer_events import CitedClaims
from .builder_evidence import section_facts
from .craft_matter import CraftMatter, MaterialRows, first_naming, section_sentences
from .material_cards import material_term
from .place_points import OriginPlace, RegisterPoint, ShownPlace

__all__ = [
    "SUPPLY_LINKS_MAX",
    "SUPPLY_MATERIALS_MAX",
    "SUPPLY_SECTION_FACTS_MAX",
    "SUPPLY_STATEMENTS_MAX",
    "SupplyOffer",
    "supply_links",
    "supply_map_block",
    "supply_offer",
]

logger = logging.getLogger(__name__)

SUPPLY_MATERIALS_MAX = 8
SUPPLY_SECTION_FACTS_MAX = 12
SUPPLY_STATEMENTS_MAX = 16
SUPPLY_LINKS_MAX = 12


@dataclass(frozen=True)
class SupplyOffer:
    materials: Mapping[str, MaterialRows]
    statements: Mapping[str, KnownClaim]

    def brief(self) -> SupplyBrief:
        return SupplyBrief(
            materials=tuple(SupplyItem(ref, _material_text(m)) for ref, m in self.materials.items()),
            statements=tuple(SupplyItem(ref, claim.text) for ref, claim in self.statements.items()),
        )


def supply_offer(matter: CraftMatter, blocks: Sequence[Block], cited: CitedClaims) -> SupplyOffer | None:
    materials = _named_materials(matter, blocks)
    own = [
        matter.records.claims.get(claim_id)
        for material in materials
        for use in material.uses
        for claim_id in use.claim_ids
    ]
    stored = [claim for claim in own if claim is not None and claim.level in FACT_LEVELS and claim.citations]
    claims = [*section_facts(blocks, cited, limit=SUPPLY_SECTION_FACTS_MAX), *stored]
    offered = list({claim.id: claim for claim in claims}.values())[:SUPPLY_STATEMENTS_MAX]
    if not offered:
        return None
    return SupplyOffer(
        materials={f"m{n}": material for n, material in enumerate(materials, start=1)},
        statements={f"c{n}": claim for n, claim in enumerate(offered, start=1)},
    )


def supply_links(
    offer: SupplyOffer, choices: Iterable[SupplyLinkChoice], *, block_id: str
) -> list[SupplyLink]:
    links: list[SupplyLink] = []
    shown: set[tuple[str, str]] = set()
    for choice in choices:
        link = _link(offer, choice, f"{block_id}.{len(links) + 1}")
        if link is None or (pair := (link.material.casefold(), link.origin.casefold())) in shown:
            continue
        shown.add(pair)
        links.append(link)
        if len(links) == SUPPLY_LINKS_MAX:
            break
    return links


def supply_map_block(
    links: Sequence[SupplyLink],
    places: Mapping[str, ShownPlace],
    *,
    block_id: str,
    boundary: DatasetRef | None = None,
) -> SupplyMapBlock | None:
    if not links:
        return None
    shown = {key: place for key, place in places.items() if boundary or isinstance(place, OriginPlace)}
    placed = [_placed(link, shown.get(link.origin.casefold())) for link in links]
    districted = any(link.district_lgd is not None for link in placed)
    try:
        return SupplyMapBlock(
            id=block_id,
            kind="supply_map",
            version=1,
            reuse=None,
            links=placed,
            datasets=[boundary] if districted and boundary is not None else [],
        )
    except ValidationError as refused:
        logger.warning("the supply map %s is refused: %s", block_id, refused)
        return None


def _named_materials(matter: CraftMatter, blocks: Sequence[Block]) -> list[MaterialRows]:
    sentences = section_sentences(blocks)
    named: list[tuple[int, MaterialRows]] = []
    for material in matter.materials:
        position = first_naming(sentences, material.surfaces(), (term.key for term in material.terms))
        if position is not None:
            named.append((position, material))
    named.sort(key=lambda pair: pair[0])
    return [material for _, material in named[:SUPPLY_MATERIALS_MAX]]


def _link(offer: SupplyOffer, choice: SupplyLinkChoice, sentence_id: str) -> SupplyLink | None:
    claim = offer.statements.get(choice.statement)
    if claim is None:
        logger.info("the supply map drops %r: not one of its statements", choice.statement)
        return None
    material = offer.materials.get(choice.material)
    if material is None and choice.material != NO_MATERIAL:
        logger.info("the supply map drops material %r: not one it was offered", choice.material)
        return None
    term = material_term(material) if material is not None else None
    name = _shown_name(material) if material is not None else choice.material_words
    if not name or name.casefold() == choice.origin.casefold():
        return None
    sentence = ExplainerSentence(
        id=sentence_id, text=claim.text, level=claim.level, citations=list(claim.citations), terms=[]
    )
    if material is not None and not _about_material(material, claim, sentence):
        logger.info("the supply map drops %r from %r: its statement is not about it", name, choice.origin)
        return None
    try:
        return SupplyLink(
            material=name,
            material_id=material.material_id if material is not None else None,
            term_key=term.key if term is not None else None,
            origin=choice.origin,
            wikidata_id=None,
            latitude=None,
            longitude=None,
            sentence=sentence,
        )
    except ValidationError as refused:
        logger.info("the supply link %r from %r is left out: %s", name, choice.origin, refused)
        return None


def _about_material(material: MaterialRows, claim: KnownClaim, sentence: ExplainerSentence) -> bool:
    own = {claim_id for use in material.uses for claim_id in use.claim_ids}
    return claim.id in own or first_naming([sentence], material.surfaces()) is not None


def _placed(link: SupplyLink, place: ShownPlace | None) -> SupplyLink:
    if place is None:
        return link
    fields = link.model_dump(by_alias=False)
    fields.update(latitude=place.latitude, longitude=place.longitude)
    if isinstance(place, RegisterPoint):
        fields.update(wikidata_id=None, district_lgd=place.district_lgd)
    else:
        fields.update(wikidata_id=place.wikidata_id, district_lgd=None)
    return SupplyLink.model_validate(fields)


def _shown_name(material: MaterialRows) -> str:
    term = material_term(material)
    return term.label if term is not None else material.name


def _material_text(material: MaterialRows) -> str:
    term = material_term(material)
    names = [name for name in (term.local_names if term is not None else ()) if name.strip()]
    lines = [f"Material: {_shown_name(material)}"]
    if names:
        lines.append(f"Also called: {', '.join(dict.fromkeys(names))}")
    return "\n".join(lines)
