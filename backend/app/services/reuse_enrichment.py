from __future__ import annotations

import logging
import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import partial
from typing import Any

from app.research.blocks import ProcessLadderBlock
from app.research.explainer import Block
from app.research.knowledge_pieces import KnowledgePiece, placed_block, shows_alike
from app.research.piece_reuse import REGION_STORY_KIND, SIMULATION_KIND, curated_piece
from app.research.sections import LADDER_DISCIPLINE, SectionSpec, block_id
from app.science.ladder import ladder_problems, process_ladder
from app.science.process_view import craft_process
from app.science.records import ProcessRecords

from .answer_events import CitedClaims
from .answer_translation import AnswerTranslation
from .claim_ledger import admission_batches
from .explainer_events import ExplainerStream
from .piece_lookup import PieceLookup, ReusedSection
from .piece_store import storable
from .section_deepening import LADDER_KIND, Deepening
from .section_enrichment import Enrichment
from .section_language import block_in_language
from .stored_fields import FLOOR_DEPTH

__all__ = [
    "CROSS_CRAFT_KINDS",
    "Floor",
    "Placed",
    "claim_texts",
    "curated_section",
    "expert_floors",
    "floor_deepening",
    "floor_sent",
    "floors_by_section",
    "kept_with_reuse",
    "placed_section",
    "process_sources",
    "reused_ladder",
]

logger = logging.getLogger(__name__)

CROSS_CRAFT_KINDS = frozenset({REGION_STORY_KIND, SIMULATION_KIND})


@dataclass(frozen=True)
class Placed:
    blocks: tuple[Block, ...] = ()
    built: tuple[Block, ...] = ()
    copies: tuple[Block, ...] = ()
    stored: tuple[Block, ...] = ()

    @property
    def kinds(self) -> frozenset[str]:
        return frozenset(block.kind for block in self.blocks)

    def stores(self, block: Block) -> bool:
        return any(kept.kind == block.kind and shows_alike(kept, block) for kept in self.stored)


@dataclass(frozen=True)
class Floor:
    placed: Placed = field(default_factory=Placed)
    cited: CitedClaims = field(default_factory=CitedClaims)
    term_names: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


def curated_section(section: ReusedSection) -> bool:
    own = [piece for piece in section.pieces if piece.craft_id is not None]
    return bool(own) and all(
        curated_piece(piece.created_from_answer_id, piece.claim_ids, section.curated) for piece in own
    )


def expert_floors(depth: str, lookup: PieceLookup) -> tuple[PieceLookup, dict[str, ReusedSection]]:
    if depth != FLOOR_DEPTH:
        return lookup, {}
    floors = {facet: section for facet, section in lookup.reused.items() if curated_section(section)}
    kept = {facet: section for facet, section in lookup.reused.items() if facet not in floors}
    return replace(lookup, reused=kept), floors


def floors_by_section(
    specs: Sequence[SectionSpec],
    floors: Mapping[str, ReusedSection],
    enrichment: Enrichment,
    process: ProcessRecords | None,
) -> dict[str, Floor]:
    return {
        spec.id: Floor(
            placed_section(spec, floors[spec.discipline], enrichment, process),
            floors[spec.discipline].cited,
            enrichment.term_names,
        )
        for spec in specs
        if spec.discipline in floors
    }


def placed_section(
    spec: SectionSpec,
    section: ReusedSection,
    enrichment: Enrichment,
    process: ProcessRecords | None = None,
    *,
    replaced: Collection[str] = frozenset(),
) -> Placed:
    stored = [placed_block(piece, block_id(spec.id, 0)) for piece in section.pieces]
    ladder = _missing_ladder(spec, stored, process)
    built = (enrichment.marked(ladder),) if ladder is not None else ()
    shown: list[Block] = list(built)
    copies: list[Block] = []
    for piece in (piece for piece in section.pieces if piece.kind not in replaced):
        block = enrichment.marked(placed_block(piece, block_id(spec.id, len(shown) + 1)))
        shown.append(block)
        if _copied(piece):
            copies.append(block.model_copy(update={"reuse": None}))
    return Placed(tuple(shown), built, tuple(copies), tuple(piece.payload for piece in section.pieces))


def reused_ladder(
    records: ProcessRecords, section_id: str, blocks: Sequence[Block]
) -> ProcessLadderBlock | None:
    cited = {claim for block in blocks for claim in block.cited_claim_ids()}
    stage_ids = [
        stage.id
        for process in craft_process(records).processes
        for stage in process.stages
        if any(str(claim.id) in cited for claim in stage.claims)
    ]
    if not stage_ids:
        return None
    ladder = process_ladder(records, block_id=block_id(section_id, 1), stage_ids=stage_ids)
    if ladder is None:
        return None
    problems = ladder_problems(ladder, records)
    if problems:
        logger.warning("the reused ladder of %s is refused: %s", section_id, "; ".join(problems))
        return None
    return ladder


def floor_deepening(placed: Placed) -> Deepening:
    claims = {uuid.UUID(claim) for block in placed.blocks for claim in block.cited_claim_ids()}
    return Deepening(first_block=len(placed.blocks) + 1, kinds=placed.kinds, claims=frozenset(claims))


async def floor_sent(
    spec: SectionSpec,
    floor: Floor,
    *,
    stream: ExplainerStream,
    translation: AnswerTranslation,
    process: ProcessRecords | None,
) -> tuple[Block, ...]:
    sources = {**process_sources(process), **floor.cited.sources}
    texts = claim_texts(process, floor.cited)
    in_language = partial(
        block_in_language,
        stream=stream,
        translation=translation,
        claim_texts=texts,
        term_names=floor.term_names,
    )
    for marker in (block.reuse for block in floor.placed.blocks if block.reuse is not None):
        await stream.trail.found_piece(marker.piece_id, title=spec.title, stored_at=marker.stored_at)
    shown: list[Block] = []
    for batch in admission_batches(floor.placed.blocks):
        shown += await stream.blocks(spec.id, batch, sources, in_language=in_language)
    return tuple(shown)


def kept_with_reuse(placed: Placed, rebuilt: Sequence[Block]) -> tuple[Block, ...]:
    added = [block for block in rebuilt if block.reuse is None and storable(block)]
    if all(placed.stores(block) or not storable(block) for block in (*placed.built, *added)):
        return ()
    return (*placed.built, *placed.copies, *added)


def process_sources(records: ProcessRecords | None) -> dict[str, dict[str, Any]]:
    stored = records.sources if records is not None else {}
    return {source_id: ref.model_dump(mode="json", by_alias=True) for source_id, ref in stored.items()}


def claim_texts(records: ProcessRecords | None, cited: CitedClaims) -> dict[uuid.UUID, str]:
    texts = {claim_id: claim.text for claim_id, claim in (records.claims if records else {}).items()}
    return texts | {claim_id: view.text for claim_id, view in cited.views.items()}


def _missing_ladder(
    spec: SectionSpec, stored: Sequence[Block], process: ProcessRecords | None
) -> ProcessLadderBlock | None:
    if process is None or spec.discipline != LADDER_DISCIPLINE:
        return None
    if any(block.kind == LADDER_KIND for block in stored):
        return None
    return reused_ladder(process, spec.id, stored)


def _copied(piece: KnowledgePiece) -> bool:
    return piece.craft_id is not None and piece.kind not in CROSS_CRAFT_KINDS
