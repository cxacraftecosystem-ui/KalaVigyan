import json
import uuid
from dataclasses import dataclass, field, replace
from typing import Any

from app.core.errors import ExternalFailure
from app.research.composition import ComposedAnswer, ComposeRequest
from app.research.retrieval import ChunkHit, ClaimHit, KnowledgeHits, KnowledgeQuery
from app.services.answer_events import CitedClaims
from app.services.knowledge_view import ClaimView
from app.voice.passages import PassageTurn, WrittenTurn
from app.voice.turns import TurnAsk, TurnTools, spoken_turn

from .fakes import (
    ALUM,
    ANSWER_ID,
    CLAIM_ID,
    CRAFT,
    QUESTION,
    STAGE_CONCEPT_ID,
    TURN_ID,
    FakeModel,
    alum_pack,
    alum_view,
    compose_reply,
    session,
    tools,
)

CHUNK_ID = uuid.UUID(int=61)
PASSAGE_ID = f"stored_passages:{CHUNK_ID}"
WRITTEN_ID = uuid.UUID(int=63)
BOOK: dict[str, Any] = {
    "id": str(uuid.UUID(int=62)),
    "kind": "BOOK",
    "title": "Block printing of Kutch",
    "authors": ["S. Writer"],
    "year": 2015,
    "doi": None,
    "url": "https://books.example.org/block-printing-of-kutch",
    "publisher": "Crafts Press",
    "licence": "CC BY 4.0",
    "attribution": None,
    "reliability": "B",
}
PASSAGE = (
    "Printers boil the mordanted cloth with alum so the madder takes a fast red. "
    "The cloth is then washed in running water."
)
QUOTE = "boil the mordanted cloth with alum so the madder takes a fast red"
SAID = "Printers boil the mordanted cloth with alum so the madder takes a fast red."
NO_ANSWER = "I found no cited answer to that about Kutch Ajrakh yet."


def passage_hit() -> ChunkHit:
    return ChunkHit(
        chunk_id=CHUNK_ID,
        source_id=uuid.UUID(BOOK["id"]),
        ordinal=0,
        locator="p. 41",
        text=PASSAGE,
        score=0.02,
        source_kind="BOOK",
        source_title=BOOK["title"],
    )


def written_view() -> ClaimView:
    citation = {
        "id": str(uuid.UUID(int=64)),
        "claimId": str(WRITTEN_ID),
        "sourceId": BOOK["id"],
        "quote": QUOTE,
        "locator": "p. 41",
        "context": None,
        "evidence": "QUOTED",
        "level": "PROVISIONAL",
    }
    return ClaimView(
        id=WRITTEN_ID,
        text=SAID,
        level="PROVISIONAL",
        concept_type="MATERIAL",
        concept_id=None,
        citations=[citation],
    )


@dataclass
class PassageSearch:
    asked: list[KnowledgeQuery] = field(default_factory=list)

    async def search(self, query: KnowledgeQuery) -> KnowledgeHits:
        self.asked.append(query)
        claim = ClaimHit(
            claim_id=CLAIM_ID,
            text="x",
            level="PROVISIONAL",
            subject_type="CONCEPT",
            subject_id=CLAIM_ID,
            score=1.0,
        )
        chunks = (passage_hit(),) if query.passages else ()
        return KnowledgeHits(craft_slug=query.craft_slug, claims=(claim,), chunks=chunks)


@dataclass
class FakePassages:
    written_claims: tuple[uuid.UUID, ...] = (WRITTEN_ID,)
    failing: bool = False
    screened_requests: list[ComposeRequest] = field(default_factory=list)
    turns: list[tuple[PassageTurn, ComposedAnswer]] = field(default_factory=list)

    async def screened(self, request: ComposeRequest) -> ComposeRequest:
        self.screened_requests.append(request)
        return request

    async def written(self, turn: PassageTurn, composed: ComposedAnswer) -> WrittenTurn:
        self.turns.append((turn, composed))
        if self.failing:
            raise ExternalFailure("the database did not answer", kind="unavailable", service="postgres")
        views = {WRITTEN_ID: written_view()} if self.written_claims else {}
        return WrittenTurn(
            claims_of=(self.written_claims,), cited=CitedClaims(views=views, sources={BOOK["id"]: BOOK})
        )


def passage_reply() -> str:
    sentence = {"text": SAID, "quotes": [{"source": PASSAGE_ID, "quote": QUOTE}]}
    return json.dumps({"sections": [{"heading": "Answer", "sentences": [sentence]}], "followUps": []})


def ask(**changes: object) -> TurnAsk:
    return TurnAsk(session(**changes), QUESTION, 1, TURN_ID, ANSWER_ID, 600.0)


def passage_tools(
    passages: FakePassages | None, search: PassageSearch, model: FakeModel | None = None
) -> TurnTools:
    pack = alum_pack(alum_view(concept_id=STAGE_CONCEPT_ID))
    chosen = model or FakeModel([passage_reply()])
    return replace(tools(pack, model=chosen), retriever=search, passages=passages)


async def test_a_hybrid_turn_asks_for_passages_its_reader_may_read() -> None:
    search = PassageSearch()
    await spoken_turn(ask(), passage_tools(FakePassages(), search))
    await spoken_turn(ask(role="RESEARCHER"), passage_tools(FakePassages(), search))
    await spoken_turn(ask(mode="VERIFIED"), passage_tools(FakePassages(), search, FakeModel([])))
    student, researcher, verified = search.asked
    assert (student.passages, student.chunk_acls) == (True, ("PUBLIC", "SIGNED_IN"))
    assert researcher.passages and set(researcher.chunk_acls) == {"PUBLIC", "SIGNED_IN", "RESEARCHER"}
    assert verified.passages is False


async def test_a_turn_speaks_a_passage_only_after_it_is_written_back() -> None:
    passages, model = FakePassages(), FakeModel([passage_reply()])
    turn = await spoken_turn(ask(), passage_tools(passages, PassageSearch(), model))
    [call] = model.calls
    assert PASSAGE_ID in call["user"] and PASSAGE in call["user"]
    [(written, composed)] = passages.turns
    assert (written.craft, written.mode, written.concept_id) == (CRAFT, "HYBRID", STAGE_CONCEPT_ID)
    assert written.passages == (passage_hit(),)
    assert [sentence.evidence_ids for section in composed.sections for sentence in section.sentences] == [
        [PASSAGE_ID]
    ]
    assert [s["text"] for s in turn.sentences] == [SAID]
    assert [c["claimId"] for c in turn.sentences[0]["citations"]] == [str(WRITTEN_ID)]
    assert turn.claim_ids == (WRITTEN_ID,) and turn.sources == (BOOK,)
    assert turn.spoken == f"{SAID} Source: Writer 2015."


async def test_a_passage_the_write_back_refuses_is_not_spoken() -> None:
    turn = await spoken_turn(ask(), passage_tools(FakePassages(written_claims=()), PassageSearch()))
    assert turn.sentences == () and turn.answer_id is None
    assert turn.spoken == NO_ANSWER


async def test_a_passage_is_not_spoken_when_its_write_back_fails() -> None:
    passages = FakePassages(failing=True)
    turn = await spoken_turn(ask(), passage_tools(passages, PassageSearch()))
    assert len(passages.turns) == 1
    assert turn.sentences == () and turn.spoken == NO_ANSWER


async def test_a_turn_that_cannot_write_back_offers_no_passage() -> None:
    model = FakeModel([compose_reply(ALUM, ALUM)])
    turn = await spoken_turn(ask(), passage_tools(None, PassageSearch(), model))
    [call] = model.calls
    assert PASSAGE_ID not in call["user"]
    assert turn.claim_ids == (CLAIM_ID,)
