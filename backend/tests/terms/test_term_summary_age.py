import json
from datetime import datetime, timedelta

from app.services.term_summaries import TermLookup

from ..answering.fakes import translation
from ..planner.fakes import FakeModel
from .fakes import CHECKED_AT, FakeResearch, FakeTermStore, golden_claims, kut_term
from .test_term_summaries import HINDI, RESEARCHED, researched_store

HALF_A_YEAR = timedelta(days=180)


def lookup_at(
    store: FakeTermStore, research: FakeResearch, moment: datetime, model: FakeModel | None = None
) -> TermLookup:
    return TermLookup(store=store, research=research, translation=translation(model), clock=lambda: moment)


async def test_a_researched_summary_half_a_year_old_is_still_served_from_the_cache() -> None:
    store, research = researched_store(), FakeResearch(RESEARCHED)
    await lookup_at(store, research, CHECKED_AT).summary("kut", "en")
    kept = await lookup_at(store, research, CHECKED_AT + HALF_A_YEAR).summary("kut", "en")
    assert (research.calls, kept.checked_at) == (1, CHECKED_AT)


async def test_a_researched_summary_older_than_half_a_year_is_researched_again_on_the_next_tap() -> None:
    store, research = researched_store(), FakeResearch(RESEARCHED)
    await lookup_at(store, research, CHECKED_AT).summary("kut", "en")
    later = CHECKED_AT + HALF_A_YEAR + timedelta(days=1)
    again = await lookup_at(store, research, later).summary("kut", "en")
    assert (research.calls, again.checked_at) == (2, later)
    assert store.cache[(kut_term().id, "en")].checked_at == later


async def test_an_old_translated_summary_is_built_again_from_a_fresh_english_one() -> None:
    store, research = researched_store(), FakeResearch(RESEARCHED)
    reply = json.dumps({"items": [{"key": "kut.1", "text": HINDI}]}, ensure_ascii=False)
    model = FakeModel([reply, reply])
    await lookup_at(store, research, CHECKED_AT, model).summary("kut", "hi")
    later = CHECKED_AT + HALF_A_YEAR + timedelta(days=1)
    again = await lookup_at(store, research, later, model).summary("kut", "hi")
    assert (research.calls, len(model.calls), again.checked_at, again.language) == (2, 2, later, "hi")


async def test_a_summary_of_stored_claims_does_not_expire_with_age() -> None:
    store = FakeTermStore({"kut": kut_term()}, stored=golden_claims())
    await lookup_at(store, FakeResearch(None), CHECKED_AT).summary("kut", "en")
    kept = await lookup_at(store, FakeResearch(None), CHECKED_AT + timedelta(days=400)).summary("kut", "en")
    assert (store.calls["defining_claims"], kept.checked_at) == (1, CHECKED_AT)
