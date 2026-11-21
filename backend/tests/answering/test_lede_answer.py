from app.services.answering import AnswerAsk

from ..planner.fakes import FakeModel
from .fakes import streamed
from .lede_search import StoredSearch
from .test_answer_flow import events
from .test_lede_flow import (
    ALUM_RED_ID,
    HARDE_ID,
    LATE_BATH,
    MORDANT,
    MORDANT_LEDE,
    REUSED_LEDE,
    SECTION_BATH,
    late_answer,
    late_lede,
    lede_pipeline,
    mordant_store,
    names,
    sections_model,
    understood_as,
)


async def test_a_late_lede_whose_answer_a_section_already_says_is_not_shown() -> None:
    reply = late_lede(SECTION_BATH, REUSED_LEDE["sentences"][0]["text"], LATE_BATH)
    found, model, store = await late_answer(reply)
    assert len(model.calls) == 1
    assert "lede" not in names(found)
    (finished,) = store.finished
    assert finished["explainer"].lede is None


async def test_the_early_lede_offers_the_answer_s_hybrid_search_findings_in_their_order() -> None:
    store = mordant_store()
    search = StoredSearch(store, order=(HARDE_ID, ALUM_RED_ID))
    model = FakeModel([MORDANT_LEDE])
    built = lede_pipeline(
        model,
        store=store,
        search=search,
        compose_model=sections_model(),
        understand_model=understood_as("CHEMISTRY"),
    )
    found = events(await streamed(AnswerAsk(question=MORDANT, depth="DETAILED"), built))
    (call,) = model.calls
    assert call["user"].index(f'ref="{HARDE_ID}"') < call["user"].index(f'ref="{ALUM_RED_ID}"')
    assert [(query.text, query.mode, query.limit) for query in search.queries] == [(MORDANT, "HYBRID", 24)]
    assert "lede" in names(found)
