import uuid
from datetime import timedelta
from typing import Any

from app.research.blocks import ReuseMarker
from app.research.knowledge_pieces import KnowledgePiece, PieceSlot, knowledge_piece
from app.research.piece_reuse import SIMULATION_FACETS, reusable_simulation, with_simulation
from app.services.block_builders import BLOCK_BUILDERS, BlockBuilders, BuilderEntry
from app.services.piece_lookup import view_states
from app.services.piece_store import storable
from app.services.simulation_builder import SIMULATION_WAIT_SECONDS, SimulationBuilder

from ..answering.test_block_builders import CARD, CARD_SOURCES, FakeBuilder, ask
from .fixtures import (
    BUILT_AT,
    STORED_AT,
    WATER_CLAIM,
    build_ask,
    golden_block,
    stored_simulation,
    water_view,
)

CRAFT_ID = uuid.UUID("54081f83-8396-5a46-a3bc-a467984eebc2")
OTHER_CLAIM = uuid.UUID("5a000000-0000-4000-8000-000000000009")


def water_prose() -> KnowledgePiece:
    prose = build_ask().blocks[0]
    slot = PieceSlot(CRAFT_ID, "GEOGRAPHY", "water:kachchh", "EXPERT")
    return knowledge_piece(prose, slot, piece_id=uuid.uuid4(), answer_id=uuid.uuid4(), created_at=STORED_AT)


def chosen(pieces: list[KnowledgePiece], **ask: Any) -> KnowledgePiece | None:
    return reusable_simulation(
        pieces,
        facet=ask.get("facet", "GEOGRAPHY"),
        depth=ask.get("depth", "EXPERT"),
        offered=ask.get("offered", {WATER_CLAIM}),
        current=view_states([water_view()]),
    )


def test_a_stored_explainer_is_chosen_only_when_every_claim_it_rests_on_is_offered_as_cited() -> None:
    piece = stored_simulation()
    assert chosen([piece]) == piece
    assert chosen([piece], depth="BASIC") == piece
    assert chosen([piece], offered={OTHER_CLAIM}) is None
    assert chosen([piece], facet="CHEMISTRY") is None
    assert chosen([piece.model_copy(update={"hidden_at": BUILT_AT})]) is None
    assert chosen([piece.model_copy(update={"superseded_by_id": uuid.uuid4()})]) is None
    assert (
        reusable_simulation([piece], facet="GEOGRAPHY", depth="EXPERT", offered={WATER_CLAIM}, current={})
        is None
    )


def test_of_several_the_newest_stored_explainer_is_chosen() -> None:
    older = stored_simulation()
    newer = stored_simulation(created_at=STORED_AT + timedelta(days=1))
    assert chosen([older, newer]) == newer


def test_a_reused_section_shows_its_stored_explainer_after_its_prose() -> None:
    prose, simulation = water_prose(), stored_simulation()
    current = view_states([water_view()])
    assert with_simulation((prose,), [simulation], depth="EXPERT", current=current) == (prose, simulation)
    hidden = simulation.model_copy(update={"hidden_at": BUILT_AT})
    assert with_simulation((prose,), [hidden], depth="EXPERT", current=current) == (prose,)
    assert with_simulation((prose,), [], depth="EXPERT", current=current) == (prose,)


def test_a_placed_piece_is_never_stored_again() -> None:
    marker = ReuseMarker(piece_id=uuid.uuid4(), stored_at=STORED_AT)
    assert storable(golden_block())
    assert not storable(golden_block(reuse=marker.model_dump(mode="json", by_alias=True)))


def test_the_simulation_builder_joins_mechanism_fields_and_may_place_a_stored_piece() -> None:
    (entry,) = [entry for entry in BLOCK_BUILDERS if entry.kind == "simulation"]
    assert entry.disciplines == SIMULATION_FACETS
    assert {
        "PROCESS",
        "CHEMISTRY",
        "PHYSICS",
        "MATERIALS",
        "GEOGRAPHY",
        "GEOLOGY",
        "CLIMATE",
    } == SIMULATION_FACETS
    assert (entry.wait_seconds, entry.places_pieces, entry.rebuilt_on_reuse) == (
        SIMULATION_WAIT_SECONDS,
        True,
        False,
    )
    assert entry.make is SimulationBuilder
    assert [other.kind for other in BLOCK_BUILDERS if other.places_pieces] == ["region_story", "simulation"]


async def test_only_an_entry_that_places_pieces_may_return_a_reuse_marked_block() -> None:
    marker = ReuseMarker(piece_id=uuid.uuid4(), stored_at=STORED_AT)
    placed = FakeBuilder(blocks=(CARD.model_copy(update={"reuse": marker}),), sources=dict(CARD_SOURCES))
    placing = BuilderEntry(
        "material_card", frozenset({"CHEMISTRY"}), lambda tools: placed, 1.0, places_pieces=True
    )
    building = BuilderEntry("material_card", frozenset({"CHEMISTRY"}), lambda tools: placed, 1.0)
    assert [block.reuse for block in (await BlockBuilders([(placing, placed)]).added(ask())).blocks] == [
        marker
    ]
    assert (await BlockBuilders([(building, placed)]).added(ask())).blocks == ()
