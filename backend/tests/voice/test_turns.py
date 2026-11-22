import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from app.core.errors import ExternalFailure
from app.research.retrieval import ClaimHit, KnowledgeHits, KnowledgeQuery
from app.schemas.voice import VoiceTranscript, VoiceTurnView
from app.voice.compose import VOICE_TURN_SCHEMA, VOICE_TURN_SYSTEM_PROMPT
from app.voice.pack import ranked_claims, searched_claims
from app.voice.transcript import StoredTranscript, transcript_view
from app.voice.turns import TurnAsk, spoken_turn

from ..contracts.golden import golden_json
from .fakes import (
    ALUM,
    ANSWER_ID,
    CLAIM_ID,
    CRAFT,
    GOLDEN_TURN,
    QUESTION,
    SOURCE,
    STAGE_CONCEPT_ID,
    STAGE_ID,
    TURN_ID,
    FakeModel,
    alum_pack,
    alum_view,
    compose_reply,
    session,
    tools,
)

RETAINED_UNTIL = datetime(2026, 12, 16, 10, 34, 12, tzinfo=UTC)


def ask(question: str = QUESTION, **changes: object) -> TurnAsk:
    return TurnAsk(session(**changes), question, 1, TURN_ID, ANSWER_ID, 600.0)


async def test_a_hybrid_turn_reproduces_the_golden_transcript_turn() -> None:
    model = FakeModel([compose_reply(ALUM, ALUM)])
    turn = await spoken_turn(ask(), tools(model=model))
    assert VoiceTurnView.model_validate(turn.view()) == VoiceTurnView.model_validate(GOLDEN_TURN)
    assert turn.parts == (ALUM, " Source: GI Journal 188.")
    [call] = model.calls
    assert call["system"] == VOICE_TURN_SYSTEM_PROMPT and call["schema"] == VOICE_TURN_SCHEMA
    assert str(CLAIM_ID) in call["user"] and QUESTION in call["user"]
    assert "Answer language: en" in call["user"]


async def test_the_stored_turn_reproduces_the_golden_transcript() -> None:
    turn = await spoken_turn(ask(), tools())
    stored = StoredTranscript([turn.view()], {SOURCE["id"]: SOURCE})
    view = transcript_view(session(retention_until=RETAINED_UNTIL), stored)
    golden = golden_json("voice.transcript.golden.json")
    assert VoiceTranscript.model_validate(view) == VoiceTranscript.model_validate(golden)


async def test_a_verified_turn_speaks_stored_claims_without_a_model() -> None:
    turn = await spoken_turn(ask(mode="VERIFIED"), tools(alum_pack(mode="VERIFIED"), model=FakeModel([])))
    assert [s["text"] for s in turn.sentences] == [ALUM]
    assert turn.sentences[0]["id"] == "t1.1"
    assert turn.claim_ids == (CLAIM_ID,)


async def test_a_sentence_failing_the_figure_check_is_not_spoken() -> None:
    model = FakeModel([compose_reply("Alum is used at 5 percent as a mordant to fasten the colours.", ALUM)])
    turn = await spoken_turn(ask(), tools(model=model))
    assert turn.sentences == () and turn.answer_id is None and turn.actions == ()
    assert turn.spoken == "I found no cited answer to that about Kutch Ajrakh yet."


async def test_a_question_no_stored_claim_touches_makes_no_model_call() -> None:
    model = FakeModel([])
    turn = await spoken_turn(ask("Which songs do the printers sing?"), tools(model=model))
    assert model.calls == [] and turn.sentences == ()


async def test_a_session_without_a_craft_asks_for_one_when_none_resolves() -> None:
    turn = await spoken_turn(ask(craft=None), tools(resolved=None))
    assert turn.spoken == "Which craft do you mean? Name it and ask again."
    assert turn.craft is None and turn.answer_id is None


async def test_a_resolved_craft_answers_but_opens_nothing_on_a_page_without_it() -> None:
    turn = await spoken_turn(ask(craft=None), tools(resolved=CRAFT))
    assert [a["name"] for a in turn.actions] == ["show_sources"]


async def test_stage_and_place_claims_open_the_page_where_the_craft_is_shown() -> None:
    stage = alum_view(concept_type="PROCESS_STAGE", concept_id=STAGE_CONCEPT_ID)
    turn = await spoken_turn(ask(), tools(alum_pack(stage, stage_of={STAGE_CONCEPT_ID: STAGE_ID})))
    assert turn.actions == (
        {"name": "show_sources", "parameters": {"answerId": str(ANSWER_ID)}},
        {"name": "open_stage", "parameters": {"stageId": str(STAGE_ID)}},
        {"name": "offer_image", "parameters": {"stageId": str(STAGE_ID)}},
    )
    place = alum_view(concept_type="ENVIRONMENTAL_CONDITION")
    turn = await spoken_turn(ask(), tools(alum_pack(place)))
    assert [a["name"] for a in turn.actions] == ["show_sources", "show_on_map"]
    assert turn.actions[1]["parameters"] == {"craftSlug": CRAFT.slug}


async def test_a_turn_renumbered_on_saving_renames_its_sentences() -> None:
    turn = (await spoken_turn(ask(), tools())).renumbered(3)
    assert turn.ordinal == 3 and turn.sentences[0]["id"] == "t3.1"


def test_asking_only_about_the_craft_ranks_its_strongest_claims() -> None:
    weak = replace(alum_view(), id=TURN_ID, text="Printers wash cloth in the river.", level="HYPOTHESIS")
    pack = alum_pack(weak, alum_view())
    assert [v.id for v in ranked_claims(pack, "Tell me about Kutch Ajrakh")] == [CLAIM_ID, TURN_ID]
    assert [v.id for v in ranked_claims(pack, "Why the river wash?")] == [TURN_ID]


@dataclass
class FakeSearch:
    found: tuple[uuid.UUID, ...] = ()
    failing: bool = False
    asked: list[KnowledgeQuery] = field(default_factory=list)

    async def search(self, query: KnowledgeQuery) -> KnowledgeHits:
        self.asked.append(query)
        if self.failing:
            raise ExternalFailure("the embedding model did not answer", kind="unavailable", service="voyage")
        hits = tuple(
            ClaimHit(
                claim_id=c, text="x", level="PROVISIONAL", subject_type="CONCEPT", subject_id=c, score=1.0
            )
            for c in self.found
        )
        return KnowledgeHits(craft_slug=query.craft_slug, claims=hits)


async def test_a_question_sharing_no_word_with_a_claim_is_answered_from_the_stored_search() -> None:
    stranger = uuid.UUID(int=77)
    search = FakeSearch(found=(stranger, CLAIM_ID))
    chosen = replace(tools(alum_pack(mode="VERIFIED"), model=FakeModel([])), retriever=search)
    turn = await spoken_turn(ask("Which songs do the printers sing?", mode="VERIFIED"), chosen)
    assert [s["text"] for s in turn.sentences] == [ALUM] and turn.claim_ids == (CLAIM_ID,)
    [query] = search.asked
    assert (query.craft_slug, query.text, query.mode, query.passages) == (
        CRAFT.slug,
        "Which songs do the printers sing?",
        "VERIFIED",
        False,
    )


async def test_a_failed_stored_search_leaves_the_word_ranking() -> None:
    chosen = replace(tools(model=FakeModel([])), retriever=FakeSearch(failing=True))
    turn = await spoken_turn(ask("Which songs do the printers sing?"), chosen)
    assert turn.sentences == () and turn.answer_id is None


def test_the_stored_search_leads_and_the_words_follow_each_claim_once() -> None:
    river = replace(alum_view(), id=TURN_ID, text="Printers wash cloth in the river.")
    pack = alum_pack(river, alum_view())
    found = KnowledgeHits(
        craft_slug=CRAFT.slug,
        claims=(
            ClaimHit(
                claim_id=CLAIM_ID,
                text="x",
                level="PROVISIONAL",
                subject_type="CONCEPT",
                subject_id=CLAIM_ID,
                score=1.0,
            ),
        ),
    )
    by_words = ranked_claims(pack, "Why the river wash?")
    assert [v.id for v in searched_claims(pack, found, by_words)] == [CLAIM_ID, TURN_ID]
    assert [v.id for v in searched_claims(pack, None, by_words)] == [TURN_ID]
    assert [v.id for v in searched_claims(pack, found, by_words, limit=1)] == [CLAIM_ID]
