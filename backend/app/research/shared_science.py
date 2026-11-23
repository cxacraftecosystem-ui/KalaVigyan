from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Self

from pydantic import Field, ValidationError, model_validator

from .base import ContractModel
from .blocks import ExplainerSentence, named_in, require_facts
from .blocks_learning import (
    COMPARE_CRAFTS_MIN,
    CONCEPT_CRAFTS_MAX,
    CONCEPT_NODES_MAX,
    ConceptCraft,
    ConceptNode,
)
from .citations import SourceRef, cited_source_ids
from .crafts import CraftRef
from .offered_facts import OfferedFact, first_naming, shown_sentence, term_marker
from .subject_keys import TermKey

__all__ = [
    "SHARED_SCIENCE_NODES_MAX",
    "SHARED_SCIENCE_SCHEMA_VERSION",
    "ConceptCraftsPage",
    "SharedConcept",
    "SharedScience",
    "TermCraftOffer",
    "TermOffer",
    "concept_crafts_page",
    "concept_node",
    "shared_concept",
    "shared_science",
]

logger = logging.getLogger(__name__)

SHARED_SCIENCE_SCHEMA_VERSION = 1
SHARED_SCIENCE_NODES_MAX = 3 * CONCEPT_NODES_MAX


class SharedScience(ContractModel):
    schema_version: Literal[1]
    craft: CraftRef
    nodes: list[ConceptNode] = Field(max_length=SHARED_SCIENCE_NODES_MAX)
    sources: list[SourceRef]

    @model_validator(mode="after")
    def _the_craft_s_shared_concepts(self) -> Self:
        keys = [node.term_key for node in self.nodes]
        if len(set(keys)) != len(keys):
            raise ValueError(f"the shared science of {self.craft.slug} shows each concept once")
        if any(all(entry.craft.slug != self.craft.slug for entry in node.crafts) for node in self.nodes):
            raise ValueError(f"the shared science of {self.craft.slug} shows only concepts it shares")
        _require_sources(self.sources, _node_sentences(self.nodes))
        return self


class SharedConcept(ContractModel):
    schema_version: Literal[1]
    node: ConceptNode
    sources: list[SourceRef]

    @model_validator(mode="after")
    def _every_craft_cited(self) -> Self:
        _require_sources(self.sources, _node_sentences([self.node]))
        return self


class ConceptCraftsPage(ContractModel):
    schema_version: Literal[1]
    term_key: TermKey
    label: str = Field(min_length=1)
    craft_count: int = Field(ge=COMPARE_CRAFTS_MIN)
    offset: int = Field(ge=0)
    crafts: list[ConceptCraft] = Field(min_length=1, max_length=CONCEPT_CRAFTS_MAX)
    sources: list[SourceRef]

    @model_validator(mode="after")
    def _a_page_of_the_crafts_sharing_the_term(self) -> Self:
        if self.offset + len(self.crafts) > self.craft_count:
            raise ValueError(f"a page of concept {self.term_key} ends within the crafts it counts")
        slugs = [entry.craft.slug for entry in self.crafts]
        if len(set(slugs)) != len(slugs):
            raise ValueError(f"a page of concept {self.term_key} lists each craft once")
        if not all(named_in(self.label, entry.sentence) for entry in self.crafts):
            raise ValueError(f"a page of concept {self.term_key} is named by each craft's cited sentence")
        sentences = [entry.sentence for entry in self.crafts]
        require_facts(f"a page of concept {self.term_key}", sentences)
        _require_sources(self.sources, sentences)
        return self


@dataclass(frozen=True)
class TermCraftOffer:
    craft: CraftRef
    concept_ids: tuple[uuid.UUID, ...]
    facts: tuple[OfferedFact, ...]


@dataclass(frozen=True)
class TermOffer:
    key: str
    label: str
    surfaces: tuple[str, ...]
    crafts: tuple[TermCraftOffer, ...]


def concept_node(offer: TermOffer, *, focus: str | None, id_prefix: str = "") -> ConceptNode | None:
    ordered = _naming_crafts(offer, focus)
    if ordered is None:
        return None
    try:
        return ConceptNode(
            term_key=offer.key,
            label=offer.label,
            crafts=_concept_crafts(offer, ordered[:CONCEPT_CRAFTS_MAX], id_prefix=id_prefix, first=1),
            craft_count=len(ordered),
        )
    except ValidationError as refused:
        logger.warning("the shared concept %s is not shown: %s", offer.key, refused)
        return None


def concept_crafts_page(
    offer: TermOffer, sources: Mapping[str, SourceRef], *, focus: str | None, offset: int
) -> ConceptCraftsPage | None:
    ordered = _naming_crafts(offer, focus)
    if ordered is None or not 0 <= offset < len(ordered):
        return None
    try:
        crafts = _concept_crafts(
            offer, ordered[offset : offset + CONCEPT_CRAFTS_MAX], id_prefix="", first=offset + 1
        )
        return ConceptCraftsPage(
            schema_version=SHARED_SCIENCE_SCHEMA_VERSION,
            term_key=offer.key,
            label=offer.label,
            craft_count=len(ordered),
            offset=offset,
            crafts=crafts,
            sources=_cited([entry.sentence for entry in crafts], sources),
        )
    except ValidationError as refused:
        logger.warning(
            "the crafts of shared concept %s from %d are not shown: %s", offer.key, offset, refused
        )
        return None


def shared_science(
    craft: CraftRef, offers: Sequence[TermOffer], sources: Mapping[str, SourceRef]
) -> SharedScience:
    nodes = [node for node in (concept_node(offer, focus=craft.slug) for offer in offers) if node is not None]
    nodes = sorted(nodes, key=lambda node: (node.label.casefold(), node.term_key))[:SHARED_SCIENCE_NODES_MAX]
    return SharedScience(
        schema_version=SHARED_SCIENCE_SCHEMA_VERSION,
        craft=craft,
        nodes=nodes,
        sources=_cited(_node_sentences(nodes), sources),
    )


def shared_concept(
    offer: TermOffer, sources: Mapping[str, SourceRef], *, focus: str | None = None
) -> SharedConcept | None:
    node = concept_node(offer, focus=focus)
    if node is None:
        return None
    return SharedConcept(
        schema_version=SHARED_SCIENCE_SCHEMA_VERSION,
        node=node,
        sources=_cited(_node_sentences([node]), sources),
    )


def _craft_order(craft: CraftRef, focus: str | None) -> tuple[bool, str, str]:
    return craft.slug != focus, craft.name.casefold(), craft.slug


def _naming_crafts(offer: TermOffer, focus: str | None) -> list[tuple[TermCraftOffer, OfferedFact]] | None:
    found: list[tuple[TermCraftOffer, OfferedFact]] = []
    for entry in offer.crafts:
        own = [fact for fact in entry.facts if fact.concept_id in entry.concept_ids]
        fact = first_naming(own, offer.label)
        if fact is not None:
            found.append((entry, fact))
    ordered = sorted(found, key=lambda pair: _craft_order(pair[0].craft, focus))
    if len(ordered) < COMPARE_CRAFTS_MIN or (focus is not None and ordered[0][0].craft.slug != focus):
        return None
    return ordered


def _concept_crafts(
    offer: TermOffer, page: Sequence[tuple[TermCraftOffer, OfferedFact]], *, id_prefix: str, first: int
) -> list[ConceptCraft]:
    marker = term_marker(offer.key, offer.surfaces)
    return [
        ConceptCraft(
            craft=entry.craft,
            concept_ids=list(entry.concept_ids),
            sentence=shown_sentence(fact, f"{id_prefix}{offer.key}.{number}", marker),
        )
        for number, (entry, fact) in enumerate(page, start=first)
    ]


def _node_sentences(nodes: Sequence[ConceptNode]) -> list[ExplainerSentence]:
    return [entry.sentence for node in nodes for entry in node.crafts]


def _cited(sentences: Sequence[ExplainerSentence], sources: Mapping[str, SourceRef]) -> list[SourceRef]:
    return [sources[source_id] for source_id in cited_source_ids(sentences)]


def _require_sources(sources: Sequence[SourceRef], sentences: Sequence[ExplainerSentence]) -> None:
    if [source.id for source in sources] != cited_source_ids(sentences):
        raise ValueError("shared science lists every cited source once, in order of first citation")
