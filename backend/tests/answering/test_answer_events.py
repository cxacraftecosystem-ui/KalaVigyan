import uuid

import httpx
import pytest

from app.core.errors import InvalidInput
from app.planner.reading import LiveSources
from app.research.composition import ComposedAnswer, ComposedSection, ComposedSentence, QuotedSpan
from app.research.write_back import WriteBackResult
from app.retrieval.indexing import EmbeddedCounts
from app.services import live_sources as live_sources_module
from app.services.answer_events import cited_claims, composed_answer_events
from app.services.live_sources import LiveSourcesStore
from app.services.research_write_back import StoredResearch, sentence_claim_ids
from app.services.write_back_plan import write_back_plan

from ..composer.fixtures import ALUM_CLAIM_ID, GUESS_CLAIM_ID, pack
from .fakes import ANSWER_ID, SOURCES, VIEWS, WRITTEN_LAKE_ID

LAKE_PAPER = "crossref:10.1000/lake"
FIGURE_TEXT = "Mordant baths held 8 g/L alum and were heated to 60 °C."
FIGURE_QUOTE = "Mordanting baths of 8 g/L alum were heated to 60 °C"
ALUM_TEXT = "Alum is the mordant that binds alizarin to cotton."
RETRACTED_TEXT = "A retracted finding about the madder bath."


def said(text: str, *, claims: tuple[uuid.UUID, ...] = (), evidence: str | None = None) -> ComposedSentence:
    refs = [str(c) for c in claims] + ([evidence] if evidence else [])
    return ComposedSentence(
        text=text,
        claim_ids=list(claims),
        evidence_ids=[evidence] if evidence else [],
        spans=[QuotedSpan(ref=refs[0], text=text.rstrip("."))],
    )


def composed(
    *sentences: ComposedSentence, open_questions: tuple[ComposedSentence, ...] = ()
) -> ComposedAnswer:
    return ComposedAnswer(
        sections=[ComposedSection(heading="Mordant", sentences=list(sentences))] if sentences else [],
        open_questions=list(open_questions),
    )


def test_each_sentence_gets_the_claim_written_for_it_and_a_pooled_one_keeps_only_its_stored_claims() -> None:
    figure = ComposedSentence(
        text=FIGURE_TEXT,
        evidence_ids=[LAKE_PAPER],
        spans=[QuotedSpan(ref=LAKE_PAPER, text=FIGURE_QUOTE)],
    )
    pooled = figure.model_copy(update={"claim_ids": [ALUM_CLAIM_ID]})
    answer = composed(said(ALUM_TEXT, claims=(ALUM_CLAIM_ID,)), figure, pooled)
    plan = write_back_plan(pack(), answer, found_by="ANSWER", answer_id=ANSWER_ID)
    assert plan.sentence_keys == (None, plan.claims[0].dedupe_key, None)
    stored = StoredResearch(
        source_ids=(),
        results=(
            WriteBackResult(dedupe_key=plan.claims[0].dedupe_key, claim_id=WRITTEN_LAKE_ID, created=False),
        ),
        skipped=plan.skipped,
        embedded=EmbeddedCounts(claims=0, chunks=0),
        sentence_keys=plan.sentence_keys,
    )
    assert sentence_claim_ids(answer, stored) == ((ALUM_CLAIM_ID,), (WRITTEN_LAKE_ID,), (ALUM_CLAIM_ID,))


def test_without_a_write_back_only_stored_claims_are_cited() -> None:
    answer = composed(said(ALUM_TEXT, claims=(ALUM_CLAIM_ID,)))
    assert sentence_claim_ids(answer, None) == ((ALUM_CLAIM_ID,),)


def test_a_write_back_of_another_answer_is_refused() -> None:
    stored = StoredResearch((), (), (), EmbeddedCounts(claims=0, chunks=0), sentence_keys=(None, None))
    with pytest.raises(InvalidInput):
        sentence_claim_ids(composed(said(ALUM_TEXT, claims=(ALUM_CLAIM_ID,))), stored)


def test_a_sentence_whose_claims_have_no_visible_citation_is_not_shown() -> None:
    answer = composed(
        said(ALUM_TEXT, claims=(ALUM_CLAIM_ID,)),
        said(RETRACTED_TEXT, claims=(uuid.UUID(int=99),)),
    )
    events = composed_answer_events(
        answer, ((ALUM_CLAIM_ID,), (uuid.UUID(int=99),)), cited_claims(VIEWS, SOURCES)
    )
    sentences = [payload["sentence"]["text"] for name, payload in events if name == "sentence"]
    assert sentences == [ALUM_TEXT]


def test_nothing_shown_is_no_events_at_all() -> None:
    answer = composed(said(RETRACTED_TEXT, claims=(uuid.UUID(int=99),)))
    assert composed_answer_events(answer, ((uuid.UUID(int=99),),), cited_claims(VIEWS, SOURCES)) == []


def test_a_sentence_resting_on_a_hypothesis_is_an_open_question_with_the_weakest_level() -> None:
    answer = composed(said("Lime may brighten alum reds.", claims=(ALUM_CLAIM_ID, GUESS_CLAIM_ID)))
    events = composed_answer_events(answer, ((ALUM_CLAIM_ID, GUESS_CLAIM_ID),), cited_claims(VIEWS, SOURCES))
    (question,) = [payload for name, payload in events if name == "open_question"]
    assert question["sentence"]["level"] == "HYPOTHESIS"
    assert [c["claimId"] for c in question["sentence"]["citations"]] == [
        str(ALUM_CLAIM_ID),
        str(GUESS_CLAIM_ID),
    ]
    assert not [name for name, _ in events if name in ("section", "sentence")]


def test_claim_lists_must_match_the_sentences() -> None:
    with pytest.raises(InvalidInput):
        composed_answer_events(
            composed(said(ALUM_TEXT, claims=(ALUM_CLAIM_ID,))), (), cited_claims(VIEWS, SOURCES)
        )


async def test_live_sources_are_built_once_per_window_on_one_client(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[httpx.AsyncClient] = []
    clients: list[httpx.AsyncClient] = []

    async def fake_live_sources(session: object, client: httpx.AsyncClient) -> LiveSources:
        built.append(client)
        return LiveSources(searchers=())

    def client_factory() -> httpx.AsyncClient:
        clients.append(httpx.AsyncClient())
        return clients[-1]

    class Sessions:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *exc: object) -> None:
            return None

    now = [0.0]
    monkeypatch.setattr(live_sources_module, "live_sources", fake_live_sources)
    store = LiveSourcesStore(ttl_seconds=600, clock=lambda: now[0], client_factory=client_factory)
    first = await store.get(Sessions)
    now[0] = 599
    assert await store.get(Sessions) is first
    now[0] = 600
    assert await store.get(Sessions) is not first
    assert len(built) == 2 and len(clients) == 1 and built[0] is built[1]
    await store.aclose()
    assert clients[0].is_closed
