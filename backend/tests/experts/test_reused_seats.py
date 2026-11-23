import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from app.research.blocks_people import ExpertViewBlock, expert_pairing_problems
from app.research.explainer import Block
from app.research.knowledge_pieces import KnowledgePiece, PieceSlot, knowledge_piece, piece_content_hash
from app.research.piece_reuse import seated_pieces
from app.research.planning import PlanRequest
from app.research.sections import SectionSpec
from app.services.block_builders import BlockBuilders
from app.services.expert_views import ExpertPanelBuilder
from app.services.piece_lookup import ReusedSection
from app.services.reused_sections import ReuseBuilds

from ..research.fixtures import AJRAKH
from .fixtures import (
    BHARMALJI,
    CLIENTS,
    FOUR_HUNDRED,
    QUESTION,
    SAHAPEDIA,
    SEVENTH_CENTURY,
    build_ask,
    cited,
    differ,
    panel_model,
    said,
    take,
    tools,
)

AT = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)
ANSWER = uuid.UUID("a5000000-0000-4000-8000-000000000001")
CRAFT_ID = uuid.UUID("a5000000-0000-4000-8000-0000000000aa")
SLOT = PieceSlot(CRAFT_ID, "HISTORY", "history:kutch-ajrakh", "EXPERT")
TRIO = ("HISTORIAN", "ANTHROPOLOGIST", "DESIGN_HISTORIAN")


def pieces_of(blocks: Sequence[Block]) -> tuple[KnowledgePiece, ...]:
    return tuple(
        knowledge_piece(block, SLOT, piece_id=uuid.uuid5(ANSWER, block.id), answer_id=ANSWER, created_at=AT)
        for block in blocks
    )


async def stored_panel(model: object) -> tuple[KnowledgePiece, ...]:
    ask = build_ask(TRIO)
    built = await ExpertPanelBuilder(tools(model)).build(ask)
    return pieces_of([*ask.blocks, *built.blocks])


def differing_trio() -> object:
    return panel_model(
        [
            take("HISTORIAN", said(BHARMALJI)),
            take("ANTHROPOLOGIST", said(CLIENTS)),
            take("DESIGN_HISTORIAN", said(BHARMALJI)),
        ],
        [differ("HISTORIAN", FOUR_HUNDRED, "ANTHROPOLOGIST", SEVENTH_CENTURY)],
    )


def views_of(pieces: Sequence[KnowledgePiece]) -> dict[str, ExpertViewBlock]:
    return {
        piece.payload.seat: piece.payload for piece in pieces if isinstance(piece.payload, ExpertViewBlock)
    }


async def test_a_reused_panel_keeps_only_the_seated_views_and_drops_what_names_the_others() -> None:
    stored = await stored_panel(differing_trio())
    assert set(views_of(stored)) == set(TRIO)
    kept = seated_pieces(stored, {"HISTORIAN", "DESIGN_HISTORIAN"})
    views = views_of(kept)
    assert [piece.kind for piece in kept] == ["prose", "expert_view", "expert_view"]
    historian = views["HISTORIAN"]
    assert (historian.differs, historian.agrees_with) == ([], ["DESIGN_HISTORIAN"])
    assert [sentence.text for sentence in historian.take] == [BHARMALJI.text]
    assert expert_pairing_problems(list(views.values())) == []
    (trimmed,) = [piece for piece in kept if piece.payload is historian]
    assert (trimmed.claim_ids, trimmed.source_ids) == ([BHARMALJI.id], [str(SAHAPEDIA.id)])
    assert trimmed.content_hash == piece_content_hash(historian)
    revalidated = KnowledgePiece.model_validate(trimmed.model_dump(mode="json", by_alias=True))
    assert (revalidated.claim_ids, revalidated.content_hash) == (trimmed.claim_ids, trimmed.content_hash)
    (design,) = [piece for piece in kept if piece.payload is views["DESIGN_HISTORIAN"]]
    assert design in stored


async def test_a_view_seated_only_for_a_difference_with_a_dropped_seat_goes_with_it() -> None:
    model = panel_model(
        [take("HISTORIAN", said(SEVENTH_CENTURY)), take("ANTHROPOLOGIST", said(CLIENTS))],
        [differ("HISTORIAN", FOUR_HUNDRED, "ANTHROPOLOGIST", SEVENTH_CENTURY)],
    )
    stored = await stored_panel(model)
    assert set(views_of(stored)) == {"HISTORIAN", "ANTHROPOLOGIST"}
    assert [piece.kind for piece in seated_pieces(stored, {"HISTORIAN"})] == ["prose"]


async def test_a_panel_whose_every_seat_is_seated_again_is_reused_whole() -> None:
    stored = await stored_panel(differing_trio())
    kept = seated_pieces(stored, set(TRIO))
    assert kept == stored and all(one is other for one, other in zip(kept, stored, strict=True))


@pytest.mark.parametrize(
    ("depth", "seats"),
    [("DETAILED", ["DESIGN_HISTORIAN", "HISTORIAN"]), ("BASIC", ["HISTORIAN"])],
)
async def test_the_reused_section_seats_the_new_understanding_s_experts_at_its_depth(
    depth: str, seats: list[str]
) -> None:
    stored = await stored_panel(differing_trio())
    request = PlanRequest(
        question=QUESTION,
        mode="HYBRID",
        craft=AJRAKH,
        depth=depth,
        seats=("HISTORIAN", "ECONOMIST", "DESIGN_HISTORIAN"),
    )
    builds = ReuseBuilds(builders=BlockBuilders(), answer_id=ANSWER, request=request)
    spec = SectionSpec(id="s2", discipline="HISTORY", title="History", order=2)
    reused = builds.seated(spec, ReusedSection(pieces=stored, cited=cited()))
    assert sorted(views_of(reused.pieces)) == seats
    assert all(view.differs == [] for view in views_of(reused.pieces).values())
