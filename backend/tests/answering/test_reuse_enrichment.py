import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.research.knowledge_pieces import KnowledgePiece, PieceSlot, knowledge_piece
from app.research.piece_reuse import answered_first
from app.research.sections import SectionSpec, section_specs
from app.research.understanding import Understanding
from app.science.reaction_player import reaction_player
from app.services.answer_events import CitedClaims
from app.services.block_builders import BLOCK_BUILDERS, BlockBuilders
from app.services.piece_lookup import PieceLookup, ReusedSection
from app.services.reuse_enrichment import (
    Placed,
    curated_section,
    expert_floors,
    floor_deepening,
    kept_with_reuse,
    placed_section,
    reused_ladder,
)
from app.services.stored_fields import FIELD_CLAIMS_MIN, every_stored_field, fields_held

from ..research.fixtures import AJRAKH
from .fakes import FakeEnrichment
from .owner_fixtures import OWNER_QUESTION, curated_ajrakh

KEPT_AT = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)


class Named:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    async def build(self, ask: object) -> object:
        raise AssertionError("not started")


def registry() -> BlockBuilders:
    return BlockBuilders([(entry, Named(entry.kind)) for entry in BLOCK_BUILDERS])


def kinds_of(builders: BlockBuilders, discipline: str) -> list[str]:
    return [entry.kind for entry, _ in builders.for_section(discipline)]


def test_a_reused_section_runs_every_builder_whose_kind_it_does_not_already_show() -> None:
    shown = {"prose", "material_card", "zoom_story", "reaction_player", "market_gi"}
    reused = registry().for_reuse(shown, depth="EXPERT")
    chemistry = kinds_of(reused, "CHEMISTRY")
    assert "material_card" not in chemistry and "zoom_story" not in chemistry
    assert {"reaction_player", "molecule_3d", "what_if", "simulation", "concept_graph", "expert_view"} <= set(
        chemistry
    )
    assert "market_gi" in kinds_of(reused, "ECONOMICS")


def test_below_expert_a_reused_section_asks_no_generated_explainer_and_no_expert_panel() -> None:
    for depth in ("BASIC", "DETAILED"):
        chemistry = kinds_of(registry().for_reuse({"prose"}, depth=depth), "CHEMISTRY")
        assert "simulation" not in chemistry and "expert_view" not in chemistry
        assert {"reaction_player", "material_card", "what_if"} <= set(chemistry)


def test_only_the_reaction_player_replaces_its_stored_block_on_reuse() -> None:
    assert registry().replaced_on_reuse("CHEMISTRY") == {"reaction_player"}
    assert registry().replaced_on_reuse("HISTORY") == frozenset()


async def test_a_reused_group_leaves_out_the_stored_player_it_rebuilds() -> None:
    curated = curated_ajrakh()
    (chemistry,) = [piece for piece in curated.pieces if piece.facet == "CHEMISTRY"]
    stored = stored_player(chemistry)
    section = ReusedSection(pieces=(chemistry, stored), cited=CitedClaims())
    enrichment = await FakeEnrichment().tools().for_answer(AJRAKH)
    spec = SectionSpec(id="s2", discipline="CHEMISTRY", title="The chemistry of Kutch Ajrakh", order=2)
    placed = placed_section(spec, section, enrichment, replaced=frozenset({"reaction_player"}))
    assert [block.kind for block in placed.blocks] == [block.kind for block in placed.copies] == ["prose"]
    assert placed.stored == (chemistry.payload, stored.payload)
    assert kept_with_reuse(placed, (player_of(curated, "s2.b2"),)) == ()


def test_a_curated_section_is_one_whose_craft_pieces_no_answer_made_from_curated_claims() -> None:
    curated = curated_ajrakh()
    (piece, *_) = curated.pieces
    marked = frozenset(piece.claim_ids)
    assert curated_section(ReusedSection(pieces=(piece,), cited=CitedClaims(), curated=marked))
    made = piece.model_copy(update={"created_from_answer_id": uuid.uuid4()})
    assert not curated_section(ReusedSection(pieces=(piece, made), cited=CitedClaims(), curated=marked))
    region = piece.model_copy(update={"craft_id": None, "created_from_answer_id": uuid.uuid4()})
    assert curated_section(ReusedSection(pieces=(piece, region), cited=CitedClaims(), curated=marked))
    orphaned = piece.model_copy(update={"id": uuid.uuid4(), "claim_ids": [uuid.uuid4()]})
    assert not curated_section(ReusedSection(pieces=(piece, orphaned), cited=CitedClaims(), curated=marked))


def test_a_group_an_answer_made_is_reused_before_the_curated_one() -> None:
    (piece, *_) = curated_ajrakh().pieces
    marked = frozenset(piece.claim_ids)
    made = piece.model_copy(update={"id": uuid.uuid4(), "created_from_answer_id": uuid.uuid4()})
    assert answered_first([(piece,), (made,)], marked) == [(made,)]
    assert answered_first([(piece,)], marked) == [(piece,)]


def test_a_piece_whose_answer_was_deleted_still_reads_as_a_reader_s() -> None:
    (piece, *_) = curated_ajrakh().pieces
    marked = frozenset(piece.claim_ids)
    orphaned = piece.model_copy(update={"id": uuid.uuid4(), "claim_ids": [uuid.uuid4()]})
    assert orphaned.created_from_answer_id is None
    assert answered_first([(piece,), (orphaned,)], marked) == [(orphaned,)]


def test_at_expert_a_curated_section_becomes_the_floor_of_a_researched_one() -> None:
    curated = curated_ajrakh()
    reused = {
        piece.facet: ReusedSection(pieces=(piece,), cited=CitedClaims(), curated=frozenset(piece.claim_ids))
        for piece in curated.pieces
    }
    lookup = PieceLookup(craft_id=curated.pieces[0].craft_id, reused=reused)
    left, floors = expert_floors("EXPERT", lookup)
    assert (dict(left.reused), set(floors)) == ({}, set(reused))
    assert expert_floors("DETAILED", lookup) == (lookup, {})


def test_research_over_a_floor_adds_only_what_the_floor_does_not_cite() -> None:
    curated = curated_ajrakh()
    (chemistry,) = [piece for piece in curated.pieces if piece.facet == "CHEMISTRY"]
    placed = Placed(blocks=(chemistry.payload,))
    deepening = floor_deepening(placed)
    assert deepening.first_block == 2 and deepening.kinds == {"prose"}
    assert deepening.claims == set(chemistry.claim_ids)


def test_a_reused_section_is_kept_again_only_when_it_gained_a_block_it_does_not_store() -> None:
    curated = curated_ajrakh()
    (process,) = [piece for piece in curated.pieces if piece.facet == "PROCESS"]
    copy = process.payload.model_copy(update={"id": "s1.b1"})
    placed = Placed(blocks=(copy,), copies=(copy,), stored=(process.payload,))
    assert kept_with_reuse(placed, ()) == ()
    assert kept_with_reuse(placed, (copy.model_copy(update={"id": "s1.b2"}),)) == ()
    ladder = reused_ladder(curated.process, "s1", (copy,))
    assert ladder is not None
    assert kept_with_reuse(placed, (ladder,)) == (copy, ladder)


def test_a_rebuilt_player_alike_the_stored_one_keeps_nothing_and_a_fuller_one_is_kept() -> None:
    curated = curated_ajrakh()
    (chemistry,) = [piece for piece in curated.pieces if piece.facet == "CHEMISTRY"]
    stored = stored_player(chemistry)
    copy = chemistry.payload.model_copy(update={"id": "s2.b1"})
    placed = Placed(blocks=(copy,), copies=(copy,), stored=(chemistry.payload, stored.payload))
    rebuilt = player_of(curated, "s2.b2")
    assert kept_with_reuse(placed, (rebuilt,)) == ()
    fewer = stored.payload.model_copy(update={"steps": stored.payload.steps[:1], "notes": []})
    older = Placed(blocks=(copy,), copies=(copy,), stored=(chemistry.payload, fewer))
    assert kept_with_reuse(older, (rebuilt,)) == (copy, rebuilt)


def test_fields_with_three_curated_claims_are_held() -> None:
    counts = {"CHEMISTRY": 12, "CLIMATE": FIELD_CLAIMS_MIN - 1, "BOTANY": FIELD_CLAIMS_MIN}
    assert fields_held(counts) == ("CHEMISTRY", "BOTANY")


def understanding(depth: str, basis: str = "MODEL") -> Understanding:
    return Understanding(
        craft=AJRAKH,
        candidates=[],
        compared=[],
        disciplines=["CHEMISTRY", "HISTORY"] if basis == "MODEL" else [],
        seats=["CHEMIST"] if basis == "MODEL" else [],
        depth=depth,
        language="en",
        basis=basis,
    )


def test_an_expert_answer_adds_every_field_the_craft_holds_after_those_asked() -> None:
    widened = every_stored_field(understanding("EXPERT"), ("PROCESS", "CHEMISTRY", "MATERIALS"))
    assert widened.disciplines == ["CHEMISTRY", "HISTORY", "PROCESS", "MATERIALS"]
    assert every_stored_field(understanding("DETAILED"), ("PROCESS",)).disciplines == ["CHEMISTRY", "HISTORY"]
    assert every_stored_field(understanding("EXPERT", "RESOLVER"), ("PROCESS",)).disciplines == ["PROCESS"]


def test_how_a_craft_works_and_its_politics_lead_the_owner_s_question() -> None:
    fields = ["OVERVIEW", "PROCESS", "CHEMISTRY", "HISTORY", "GEOGRAPHY", "ECONOMICS", "DESIGN"]
    ordered = [
        spec.discipline
        for spec in section_specs(fields, "EXPERT", question=OWNER_QUESTION, craft_name="Kutch Ajrakh")
    ]
    assert ordered == ["PROCESS", "CHEMISTRY", "HISTORY", "GEOGRAPHY", "ECONOMICS", "OVERVIEW", "DESIGN"]
    politics = section_specs(
        ["DESIGN", "ECONOMICS", "HISTORY"], "EXPERT", question="What are the politics of Ajrakh?"
    )
    assert [spec.discipline for spec in politics] == ["ECONOMICS", "HISTORY", "DESIGN"]


@pytest.mark.parametrize(
    ("question", "ordered"),
    [
        ("How does the GI tag work for Ajrakh?", ["ECONOMICS", "HISTORY", "PROCESS"]),
        ("Where do Ajrakh printers work?", ["ECONOMICS", "HISTORY", "PROCESS"]),
        ("How does Kutch Ajrakh work?", ["PROCESS", "ECONOMICS", "HISTORY"]),
        ("Show me how this works", ["PROCESS", "ECONOMICS", "HISTORY"]),
    ],
)
def test_work_leads_with_the_process_only_when_asked_how_the_craft_works(
    question: str, ordered: list[str]
) -> None:
    specs = section_specs(
        ["ECONOMICS", "HISTORY", "PROCESS"], "DETAILED", question=question, craft_name="Kutch Ajrakh"
    )
    assert [spec.discipline for spec in specs] == ordered


def player_of(curated: Any, block_id: str) -> Any:
    player = reaction_player(curated.process, block_id=block_id)
    assert player is not None
    return player


def stored_player(beside: KnowledgePiece) -> KnowledgePiece:
    player = player_of(curated_ajrakh(), "s2.reactions")
    slot = PieceSlot(beside.craft_id, beside.facet, beside.topic_key, beside.depth)
    return knowledge_piece(
        player, slot, piece_id=uuid.uuid4(), answer_id=uuid.uuid4(), created_at=KEPT_AT
    ).model_copy(update={"created_from_answer_id": None})
