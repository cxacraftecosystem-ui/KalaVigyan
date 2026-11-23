import uuid

import pytest

from app.research.planning import ResearchShare, split_share
from app.research.sections import section_specs
from app.science.ladder import process_ladder
from app.services.answer_events import cited_claims
from app.services.answer_translation import translated_block
from app.services.research_ledger import ResearchLedger
from app.services.section_blocks import (
    BlockRefused,
    KeptSentence,
    prose_block,
    prose_problems,
    section_sentences,
)
from app.services.stated_names import register_places_named, unstated_names

from ..planner.fakes import FakeModel
from ..science.golden_process import KUT, RED, golden_records, stage_id
from .fakes import ALUM_CLAIM_ID, GUESS_CLAIM_ID, SOURCES, VIEWS, WRITTEN_LAKE_ID, translation
from .test_translation_flow import reply

CITED = cited_claims(list(VIEWS), SOURCES)


def kept(text: str, *claims: uuid.UUID) -> KeptSentence:
    return KeptSentence(text, claims, (), False)


def test_a_prose_block_carries_each_sentence_with_its_stored_citations() -> None:
    block = prose_block("s1.b1", [kept("Alum is the mordant.", ALUM_CLAIM_ID)], CITED)
    (sentence,) = block.sentences
    assert (sentence.id, sentence.level, sentence.terms) == ("s1.b1.1", "REVIEWED", [])
    assert [c.id for c in sentence.citations] == ["c0000000-0000-4000-8000-000000000001"]


def test_a_block_with_an_uncited_sentence_is_refused_whole() -> None:
    sentences = [kept("Alum is the mordant.", ALUM_CLAIM_ID), kept("Alum came from Gujarat.")]
    with pytest.raises(BlockRefused) as refused:
        prose_block("s1.b1", sentences, CITED)
    assert refused.value.problems == ("sentence 2 cites no stored claim",)


def test_a_figure_no_cited_claim_or_quote_holds_refuses_the_block() -> None:
    sentences = [kept("Mordant baths held 9 g/L alum.", WRITTEN_LAKE_ID)]
    assert prose_problems(sentences, CITED) == ["sentence 1 states 9, which no cited claim or quote holds"]


@pytest.mark.parametrize(
    ("text", "named"),
    [
        ("Mordant baths held 8 g/L alum in March.", "March"),
        ("Mordant baths held 8 g/L alum through the monsoon.", "monsoon"),
        ("Mordant baths held 8 g/L alum in Kachchh.", "Kachchh"),
        ("Mordant baths held 8 g/L alum in Gujarat.", "Gujarat"),
    ],
)
def test_a_time_or_place_no_cited_claim_or_quote_states_refuses_the_block(text: str, named: str) -> None:
    assert prose_problems([kept(text, WRITTEN_LAKE_ID)], CITED) == [
        f"sentence 1 names {named}, which no cited claim or quote states"
    ]


def test_a_place_a_quote_states_or_a_compass_word_is_no_problem() -> None:
    assert (
        unstated_names("Dyers in Kachchh work in winter.", ["dyers of kachchh work in the cold season"]) == []
    )
    assert unstated_names("West of the river, North of the town.", []) == []
    assert register_places_named("Bhuj is in Kachchh, Gujarat; Mon is in Nagaland.") == [
        "Kachchh",
        "Gujarat",
        "Mon",
        "Nagaland",
    ]


def test_a_district_written_by_its_other_name_is_read_as_its_register_place() -> None:
    assert register_places_named("Ajrakh of Kutch, Gujarat, as Kachchh's printers make it.") == [
        "Kachchh",
        "Gujarat",
    ]
    assert (
        unstated_names("Dyers in Kutch work in winter.", ["dyers of kachchh work in the cold season"]) == []
    )
    assert (
        unstated_names("Dyers in Kachchh work in winter.", ["dyers of kutch work in the cold season"]) == []
    )
    assert unstated_names("Dyers in Kachchh print.", ["dyers of barmer print"]) == ["Kachchh"]
    assert unstated_names("Kutch Ajrakh is printed in Barmer.", ["ajrakh is printed in barmer"]) == []


def test_a_regional_month_a_sentence_names_must_be_stated_by_a_support_in_any_spelling() -> None:
    assert unstated_names("Wear is bought in the month of Kartik.", ["bought at kartika fairs"]) == []
    assert unstated_names("Wear is bought in the month of Kartik.", ["bought around diwali"]) == ["kartika"]
    assert unstated_names("Kartik Chandra Pal made the statue.", ["a statue by pal"]) == []


def test_a_sentence_naming_what_its_sources_do_not_is_dropped_alone() -> None:
    sentences = [
        kept("Alum is the mordant.", ALUM_CLAIM_ID),
        kept("Mordant baths held 8 g/L alum in March.", WRITTEN_LAKE_ID),
        kept("Lime in the wash water may brighten the red in Gujarat.", GUESS_CLAIM_ID),
    ]
    split = section_sentences(sentences, CITED)
    assert ([s.text for s in split.facts], split.open_questions) == (["Alum is the mordant."], ())


async def test_translating_a_ladder_changes_its_sentences_only_and_keeps_their_citations() -> None:
    records = golden_records()
    ladder = process_ladder(records, block_id="s1.b1", stage_ids=[stage_id(KUT), stage_id(RED)])
    payload = ladder.model_dump(mode="json", by_alias=True, exclude_unset=True)
    texts = {claim_id: claim.text for claim_id, claim in records.claims.items()}
    model = FakeModel(
        [reply(**{"s1.b1.1": "काट से काली छपाई होती है।", "s1.b1.2": "लाल रंगाई तांबे के बर्तन में होती है।"})]
    )
    shown = await translated_block(payload, language="hi", translation=translation(model), claim_texts=texts)
    before = [s for stage in payload["stages"] for s in stage["sentences"]]
    after = [s for stage in shown["stages"] for s in stage["sentences"]]
    assert [s["text"] for s in after] == ["काट से काली छपाई होती है।", "लाल रंगाई तांबे के बर्तन में होती है।"]
    assert [s["original"] for s in after] == [s["text"] for s in before]
    assert [s["citations"] for s in after] == [s["citations"] for s in before]
    assert [stage["name"] for stage in shown["stages"]] == [stage["name"] for stage in payload["stages"]]
    assert [stage["conditions"] for stage in shown["stages"]] == [
        stage["conditions"] for stage in payload["stages"]
    ]


def test_sections_keep_the_most_important_fields_and_put_the_full_process_last() -> None:
    fields = ["PROCESS", "CHEMISTRY", "PROCESS", "HISTORY", "CLIMATE", "ECOLOGY", "DESIGN"]
    basic = section_specs(fields, "BASIC", craft_name="Kutch Ajrakh")
    assert [(s.id, s.discipline, s.title, s.order) for s in basic] == [
        ("s1", "CHEMISTRY", "The chemistry behind Kutch Ajrakh", 1),
        ("s2", "HISTORY", "Where Kutch Ajrakh comes from", 2),
        ("s3", "CLIMATE", "The weather Kutch Ajrakh works with", 3),
        ("s4", "PROCESS", "How Kutch Ajrakh is made", 4),
    ]
    assert [(s.discipline, s.title) for s in section_specs([], "EXPERT")] == [
        ("OVERVIEW", "What the craft is")
    ]


def test_a_research_budget_splits_with_the_remainder_to_the_first_sections() -> None:
    total = ResearchShare(queries=8, native_queries=3, fetches=20)
    shares = [(s.queries, s.native_queries, s.fetches) for s in split_share(total, 3)]
    assert shares == [(3, 1, 7), (3, 1, 7), (2, 1, 6)]


def test_the_ledger_hands_out_no_more_than_the_depth_budget() -> None:
    ledger = ResearchLedger(ResearchShare(queries=2, native_queries=0, fetches=5), (1, 1, 1))
    first = ledger.take(ResearchShare(queries=2, native_queries=0, fetches=5))
    assert (first.queries, first.fetches) == (2, 5)
    assert ledger.take_fresh(ResearchShare(queries=0, native_queries=0, fetches=0)) is None
    ledger.give_back(ResearchShare(queries=1, native_queries=0, fetches=3))
    fresh = ledger.take_fresh(ResearchShare(queries=0, native_queries=0, fetches=0))
    assert fresh is not None and (fresh.queries, fresh.fetches) == (1, 2)
    assert (ledger.left.queries, ledger.left.fetches) == (0, 1)


def test_a_later_section_takes_a_fair_part_of_the_budget_earlier_sections_left() -> None:
    ledger = ResearchLedger(ResearchShare(queries=4, native_queries=0, fetches=10), (1,) * 6)
    assert [(s.queries, s.fetches) for s in ledger.shares] == [(1, 2), (1, 2), (1, 2), (1, 2), (0, 1), (0, 1)]
    taken = [ledger.take_section(share) for share in ledger.shares[:4]]
    assert [(s.queries, s.fetches) for s in taken] == [(1, 2), (1, 2), (1, 2), (1, 2)]
    ledger.give_back(taken[0])
    ledger.give_back(taken[1])
    fifth = ledger.take_section(ledger.shares[4])
    sixth = ledger.take_section(ledger.shares[5])
    assert [(s.queries, s.fetches) for s in (fifth, sixth)] == [(1, 3), (1, 3)]
    assert ledger.left == ResearchShare(queries=0, native_queries=0, fetches=0)


def test_a_section_that_starts_early_never_takes_the_share_of_one_still_waiting() -> None:
    ledger = ResearchLedger(ResearchShare(queries=2, native_queries=0, fetches=5), (1, 1, 1))
    first, second, third = ledger.shares
    taken = [ledger.take_section(third), ledger.take_section(first), ledger.take_section(second)]
    assert [(s.queries, s.fetches) for s in taken] == [(0, 1), (1, 2), (1, 2)]
