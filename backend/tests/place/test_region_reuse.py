import dataclasses
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.research.blocks_place import RegionStoryBlock
from app.research.knowledge_pieces import KnowledgePiece, PieceSlot, knowledge_piece, piece_slot
from app.research.piece_reuse import ClaimState, with_region_story
from app.research.piece_topics import TopicSubjects
from app.services import piece_store, place_builders
from app.services.answer_events import CitedClaims
from app.services.block_builders import BLOCK_BUILDERS, BlockBuilders
from app.services.piece_lookup import PieceAsk
from app.services.piece_store import SqlPieceStore
from app.services.place_builders import RegionStoryBuilder
from app.services.region_story import RegionOffer

from ..answering.fakes import (
    SOURCES,
    UNDERSTOOD_REPLY,
    VIEWS,
    FakeResearch,
    pipeline,
    streamed,
    understanding_model,
)
from ..answering.piece_fakes import CRAFT_ID, MemoryPieces
from ..answering.test_answer_flow import REPLY, events
from ..answering.test_piece_reuse_flow import asked
from ..composer.fixtures import replacements
from ..research.fixtures import AJRAKH
from .fixtures import KACHCHH, golden_story, kachchh_offer, no_session, place_tools, story_model, water_prose

KEPT_AT = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
FIRST_ANSWER = uuid.UUID(int=10)
OTHER_ANSWER = uuid.UUID(int=11)
WATER = "water:kachchh"
BASIN = "water:basin-3"
STORY_REPLY = {
    "river": "r1",
    "steps": [{"claim": "c1", "district": f"d{KACHCHH}"}],
    "layers": ["river-density"],
}


def stored(block: Any, slot: PieceSlot, *, answer: uuid.UUID, at: datetime = KEPT_AT) -> KnowledgePiece:
    return knowledge_piece(
        block, piece_slot(block, slot), piece_id=uuid.uuid4(), answer_id=answer, created_at=at
    )


def story_piece(*, answer: uuid.UUID = FIRST_ANSWER, depth: str = "EXPERT", at: datetime = KEPT_AT) -> Any:
    block = RegionStoryBlock.model_validate(golden_story())
    return stored(block, PieceSlot(CRAFT_ID, "GEOGRAPHY", WATER, depth), answer=answer, at=at)


def prose_piece() -> KnowledgePiece:
    return stored(water_prose(), PieceSlot(CRAFT_ID, "GEOGRAPHY", WATER, "EXPERT"), answer=FIRST_ANSWER)


def visible(*pieces: KnowledgePiece) -> dict[uuid.UUID, ClaimState]:
    found: dict[uuid.UUID, ClaimState] = {}
    for piece in pieces:
        for citation in piece.payload.citations():
            claim = uuid.UUID(citation.claim_id)
            held = found.get(claim, ClaimState(citation.level, frozenset()))
            found[claim] = ClaimState(citation.level, held.citation_ids | {citation.id})
    return found


def test_a_stored_region_story_joins_its_reused_section_after_the_prose() -> None:
    prose, story = prose_piece(), story_piece()
    assert (story.craft_id, story.topic_key) == (None, BASIN)
    shown = with_region_story((prose,), [story], depth="EXPERT", current=visible(prose, story))
    assert [piece.kind for piece in shown] == ["prose", "region_story"]


def test_the_story_kept_with_the_section_wins_over_a_newer_one() -> None:
    prose, own = prose_piece(), story_piece()
    newer = story_piece(answer=OTHER_ANSWER, at=datetime(2026, 11, 17, 10, 0, tzinfo=UTC))
    shown = with_region_story((prose,), [newer, own], depth="EXPERT", current=visible(prose, own))
    assert shown[1].id == own.id
    elsewhere = prose.model_copy(update={"created_from_answer_id": None})
    assert (
        with_region_story((elsewhere,), [newer, own], depth="EXPERT", current=visible(prose))[1].id
        == newer.id
    )


@pytest.mark.parametrize(
    "case",
    ["stale", "shallower", "claim gone", "craft piece"],
)
def test_a_region_story_that_fails_the_reuse_rule_is_left_out(case: str) -> None:
    prose, story = prose_piece(), story_piece()
    current = visible(prose, story)
    if case == "stale":
        story = story.model_copy(update={"stale_since": KEPT_AT})
    elif case == "shallower":
        story = story_piece(depth="BASIC")
    elif case == "claim gone":
        current.pop(uuid.UUID(story.payload.steps[0].sentence.citations[0].claim_id))
    else:
        story = story.model_copy(update={"craft_id": CRAFT_ID})
    assert with_region_story((prose,), [story], depth="EXPERT", current=current) == (prose,)


def geography_pipeline(pieces: MemoryPieces, research: FakeResearch | None = None) -> Any:
    entry = next(entry for entry in BLOCK_BUILDERS if entry.kind == "region_story")
    builder = RegionStoryBuilder(place_tools(story_model(STORY_REPLY)))
    understand = {**UNDERSTOOD_REPLY, "disciplines": ["GEOGRAPHY"], "seats": ["HYDROLOGIST"]}
    answer = pipeline(
        replies=[REPLY, replacements()],
        pieces=pieces,
        research=research,
        understand_model=understanding_model(understand),
    )
    return dataclasses.replace(answer, builders=BlockBuilders([(entry, builder)]))


@pytest.fixture
def offered(monkeypatch: pytest.MonkeyPatch) -> None:
    async def loaded(session: Any) -> bool:
        return True

    async def offer(session: Any, craft_slug: str) -> RegionOffer:
        return kachchh_offer()

    monkeypatch.setattr(place_builders, "rivers_loaded", loaded)
    monkeypatch.setattr(place_builders, "region_offer", offer)


async def test_a_region_story_is_kept_across_crafts_and_reused_with_its_section(offered: None) -> None:
    pieces = MemoryPieces(views=list(VIEWS), sources=dict(SOURCES))
    first = events(await streamed(asked(), geography_pipeline(pieces)))
    shown = [(payload["block"]["id"], payload["block"]["kind"]) for name, payload in first if name == "block"]
    assert shown == [("s1.b1", "prose"), ("s1.b2", "region_story")]
    story = next(piece for piece in pieces.current() if piece.kind == "region_story")
    assert (story.craft_id, story.facet, story.topic_key) == (None, "GEOGRAPHY", BASIN)
    research = FakeResearch()
    again = events(await streamed(asked(), geography_pipeline(pieces, research)))
    assert research.requests == []
    reused = [
        (payload["block"]["id"], payload["block"]["kind"], payload["block"]["reuse"]["pieceId"])
        for name, payload in again
        if name == "block"
    ]
    assert [(block_id, kind) for block_id, kind, _ in reused] == [
        ("s1.b1", "prose"),
        ("s1.b2", "region_story"),
    ]
    assert reused[1][2] == str(story.id)


@pytest.mark.parametrize(
    ("facets", "looked_up"),
    [(("CHEMISTRY", "GEOGRAPHY"), [["GEOGRAPHY"]]), (("CHEMISTRY", "HISTORY"), [])],
)
async def test_region_stories_are_looked_up_for_the_geography_facet_only(
    monkeypatch: pytest.MonkeyPatch, facets: tuple[str, ...], looked_up: list[list[str]]
) -> None:
    asked_for: list[list[str]] = []

    async def craft(session: Any, slug: str) -> Any:
        return SimpleNamespace(id=CRAFT_ID, slug=slug)

    async def subjects(session: Any, found: Any, question: str) -> TopicSubjects:
        return TopicSubjects(craft_slug=found.slug)

    async def candidates(session: Any, craft_id: uuid.UUID, topics: Any) -> list[KnowledgePiece]:
        return [prose_piece()]

    async def regions(session: Any, found: Any, region_facets: list[str]) -> list[KnowledgePiece]:
        asked_for.append(list(region_facets))
        return []

    async def states(session: Any, pieces: Any, **_kwargs: Any) -> tuple[dict, CitedClaims]:
        return {}, CitedClaims()

    async def simulations(session: Any, claim_ids: Any, simulation_facets: Any) -> list[KnowledgePiece]:
        return []

    monkeypatch.setattr(piece_store.knowledge_view, "resolve_craft", craft)
    for name, fake in (
        ("topic_subjects", subjects),
        ("candidate_pieces", candidates),
        ("region_story_pieces", regions),
        ("claim_states", states),
        ("simulation_pieces", simulations),
    ):
        monkeypatch.setattr(piece_store, name, fake)
    store = SqlPieceStore(no_session, embed=None, shield=None)
    await store.reusable(PieceAsk(question="Why water?", craft=AJRAKH, facets=facets, depth="EXPERT"))
    assert asked_for == looked_up
