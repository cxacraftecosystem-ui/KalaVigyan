from __future__ import annotations

import re
import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from .knowledge_pieces import KnowledgePiece, ReuseAsk, reuse_refusal

__all__ = [
    "PIECE_BLOCK_ORDER",
    "REGION_STORY_FACETS",
    "REGION_STORY_KIND",
    "SIMULATION_FACETS",
    "SIMULATION_KIND",
    "ClaimState",
    "answered_first",
    "curated_piece",
    "piece_group_key",
    "reusable_groups",
    "reusable_simulation",
    "visible_as_cited",
    "with_region_story",
    "with_simulation",
]

REGION_STORY_KIND = "region_story"
REGION_STORY_FACETS = frozenset({"GEOGRAPHY"})
SIMULATION_KIND = "simulation"
SIMULATION_FACETS = frozenset(
    {"PROCESS", "CHEMISTRY", "PHYSICS", "MATERIALS", "GEOGRAPHY", "GEOLOGY", "CLIMATE"}
)
PIECE_BLOCK_ORDER = (
    "process_ladder",
    "prose",
    "region_story",
    "map_layer",
    "seasons",
    "climate_risk",
    "supply_map",
    "measure",
    "market_gi",
    "reaction_player",
    "material_card",
    "molecule_3d",
    "expert_view",
    "artisan_voice",
    "what_if",
    "simulation",
    "zoom_story",
    "timeline_map",
    "compare",
    "concept_graph",
    "images",
)
DIGITS = re.compile(r"(\d+)")


@dataclass(frozen=True)
class ClaimState:
    level: str
    citation_ids: frozenset[str]


def visible_as_cited(piece: KnowledgePiece, current: Mapping[uuid.UUID, ClaimState]) -> set[uuid.UUID]:
    cited: dict[uuid.UUID, set[str]] = {}
    levels: dict[uuid.UUID, set[str]] = {}
    for citation in piece.payload.citations():
        claim_id = uuid.UUID(citation.claim_id)
        cited.setdefault(claim_id, set()).add(citation.id)
        levels.setdefault(claim_id, set()).add(citation.level)
    return {
        claim_id
        for claim_id, citation_ids in cited.items()
        if claim_id in current
        and citation_ids <= current[claim_id].citation_ids
        and levels[claim_id] == {current[claim_id].level}
    }


def piece_group_key(piece: KnowledgePiece) -> tuple[str, uuid.UUID]:
    return piece.facet, piece.created_from_answer_id or piece.id


def curated_piece(
    answer_id: uuid.UUID | None, claim_ids: Collection[uuid.UUID], curated: Collection[uuid.UUID]
) -> bool:
    return answer_id is None and bool(claim_ids) and all(claim_id in curated for claim_id in claim_ids)


def answered_first(
    groups: Sequence[tuple[KnowledgePiece, ...]], curated: Collection[uuid.UUID]
) -> list[tuple[KnowledgePiece, ...]]:
    answered = [
        group
        for group in groups
        if not all(curated_piece(piece.created_from_answer_id, piece.claim_ids, curated) for piece in group)
    ]
    return answered or list(groups)


def reusable_groups(
    pieces: Sequence[KnowledgePiece], ask: ReuseAsk, current: Mapping[uuid.UUID, ClaimState]
) -> list[tuple[KnowledgePiece, ...]]:
    groups: dict[tuple[str, uuid.UUID], list[KnowledgePiece]] = {}
    for piece in pieces:
        if piece.facet == ask.facet:
            groups.setdefault(piece_group_key(piece), []).append(piece)
    return [
        tuple(sorted(group, key=_reading_order))
        for group in groups.values()
        if all(reuse_refusal(piece, ask, visible_as_cited(piece, current)) is None for piece in group)
    ]


def with_region_story(
    group: Sequence[KnowledgePiece],
    regions: Sequence[KnowledgePiece],
    *,
    depth: str,
    current: Mapping[uuid.UUID, ClaimState],
) -> tuple[KnowledgePiece, ...]:
    facet = group[0].facet
    usable = [
        piece
        for piece in regions
        if piece.kind == REGION_STORY_KIND
        and piece.craft_id is None
        and reuse_refusal(
            piece,
            ReuseAsk(craft_id=None, facet=facet, topic_key=piece.topic_key, depth=depth),
            visible_as_cited(piece, current),
        )
        is None
    ]
    if not usable:
        return tuple(group)
    answer = group[0].created_from_answer_id
    same = [piece for piece in usable if answer is not None and piece.created_from_answer_id == answer]
    chosen = (same or usable)[0]
    return tuple(sorted([*group, chosen], key=_reading_order))


def reusable_simulation(
    pieces: Sequence[KnowledgePiece],
    *,
    facet: str,
    depth: str,
    offered: Collection[uuid.UUID],
    current: Mapping[uuid.UUID, ClaimState],
) -> KnowledgePiece | None:
    usable = [
        piece
        for piece in pieces
        if piece.kind == SIMULATION_KIND
        and set(piece.claim_ids) <= set(offered)
        and reuse_refusal(
            piece,
            ReuseAsk(craft_id=None, facet=facet, topic_key=piece.topic_key, depth=depth),
            visible_as_cited(piece, current),
        )
        is None
    ]
    return max(usable, key=lambda piece: (len(piece.claim_ids), piece.created_at), default=None)


def with_simulation(
    group: Sequence[KnowledgePiece],
    simulations: Sequence[KnowledgePiece],
    *,
    depth: str,
    current: Mapping[uuid.UUID, ClaimState],
) -> tuple[KnowledgePiece, ...]:
    offered = {claim for piece in group for claim in piece.claim_ids}
    chosen = reusable_simulation(
        simulations, facet=group[0].facet, depth=depth, offered=offered, current=current
    )
    if chosen is None or chosen in group:
        return tuple(group)
    return tuple(sorted([*group, chosen], key=_reading_order))


def _reading_order(piece: KnowledgePiece) -> tuple[int, list[tuple[int, int, str]]]:
    shown = [
        (0, int(part), "") if part.isdigit() else (1, 0, part) for part in DIGITS.split(piece.payload.id)
    ]
    return PIECE_BLOCK_ORDER.index(piece.kind), shown
