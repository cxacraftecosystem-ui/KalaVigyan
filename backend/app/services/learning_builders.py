from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from app.models.enums import DISCIPLINES
from app.research.blocks import ExplainerSentence
from app.research.blocks_learning import ConceptGraphBlock
from app.research.craft_compare import compare_block
from app.research.crafts import CraftRef
from app.research.explainer import Block
from app.research.retrieval import EVERY_CHUNK_ACLS
from app.research.shared_science import concept_node

from . import knowledge_view
from .builder_evidence import sources_beyond
from .builder_interface import BuildAsk, BuilderTools, Built
from .craft_compare import CompareOffers, comparison_offers
from .shared_concepts import TermOffers, term_ids_of, term_offers

__all__ = [
    "COMPARE_FIELDS",
    "COMPARE_SECTION_ROWS",
    "CONCEPT_GRAPH_FIELDS",
    "CONCEPT_GRAPH_SECTION_NODES",
    "CompareBuilder",
    "CompareLoader",
    "ConceptGraphBuilder",
    "GraphLoader",
    "section_term_keys",
]

COMPARE_FIELDS = frozenset(DISCIPLINES)
COMPARE_SECTION_ROWS = 4
CONCEPT_GRAPH_FIELDS = frozenset({"CHEMISTRY", "PHYSICS", "MATERIALS", "GEOGRAPHY"})
CONCEPT_GRAPH_SECTION_NODES = 4

CompareLoader = Callable[[Sequence[CraftRef], Sequence[str]], Awaitable[CompareOffers]]
GraphLoader = Callable[[Sequence[str], CraftRef], Awaitable[TermOffers]]


class CompareBuilder:
    def __init__(self, tools: BuilderTools, *, offers: CompareLoader | None = None) -> None:
        self._offers = offers or _stored_comparison(tools)

    async def build(self, ask: BuildAsk) -> Built:
        request = ask.request
        if request.craft is None or not request.compared:
            return Built()
        facets = (ask.section.discipline,)
        found = await self._offers((request.craft, *request.compared), facets)
        block = compare_block(
            found.crafts,
            found.terms,
            facets=facets,
            block_id=f"{ask.section.id}.compare",
            rows_max=COMPARE_SECTION_ROWS,
        )
        if block is None:
            return Built()
        return Built((block,), sources_beyond([block], found.sources, ask.cited))


class ConceptGraphBuilder:
    def __init__(self, tools: BuilderTools, *, offers: GraphLoader | None = None) -> None:
        self._offers = offers or _stored_concepts(tools)

    async def build(self, ask: BuildAsk) -> Built:
        craft = ask.request.craft
        keys = section_term_keys(ask.blocks)
        if craft is None or not keys:
            return Built()
        found = await self._offers(keys, craft)
        block_id = f"{ask.section.id}.shared"
        nodes = [
            node
            for node in (
                concept_node(offer, focus=craft.slug, id_prefix=f"{block_id}.") for offer in found.offers
            )
            if node is not None
        ][:CONCEPT_GRAPH_SECTION_NODES]
        if not nodes:
            return Built()
        block = ConceptGraphBlock(
            id=block_id, kind="concept_graph", version=1, reuse=None, focus=craft, nodes=nodes
        )
        return Built((block,), sources_beyond([block], found.sources, ask.cited))


def section_term_keys(blocks: Sequence[Block]) -> list[str]:
    return list(
        dict.fromkeys(
            span.term_key
            for block in blocks
            for sentence in block.cited_sentences()
            if isinstance(sentence, ExplainerSentence)
            for span in sentence.terms
        )
    )


def _stored_comparison(tools: BuilderTools) -> CompareLoader:
    async def load(crafts: Sequence[CraftRef], facets: Sequence[str]) -> CompareOffers:
        async with tools.sessions() as session:
            rows = [await knowledge_view.resolve_craft(session, craft.slug) for craft in crafts]
            known = [row for row in rows if row is not None]
            if len(known) != len(crafts):
                return CompareOffers()
            return await comparison_offers(session, known, facets, acls=EVERY_CHUNK_ACLS)

    return load


def _stored_concepts(tools: BuilderTools) -> GraphLoader:
    async def load(keys: Sequence[str], craft: CraftRef) -> TermOffers:
        async with tools.sessions() as session:
            row = await knowledge_view.resolve_craft(session, craft.slug)
            if row is None:
                return TermOffers()
            return await term_offers(session, await term_ids_of(session, keys), acls=EVERY_CHUNK_ACLS)

    return load
