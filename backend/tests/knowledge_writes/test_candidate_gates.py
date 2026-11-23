import pytest

from app.research.candidate_gates import (
    Candidate,
    CitedSource,
    FactComparison,
    NoveltyVerdict,
    close_facts,
    duplicate_outcome,
    held_twin,
    novelty_outcome,
    quote_gate,
    source_gate,
)

from .fakes import PAGE_TEXT, PAGE_URL, QUOTE, SECOND_QUOTE, STATEMENT, fact_id, held

CANDIDATE = Candidate(ref="c1", statement=STATEMENT, field="PROCESS")


def cited(*quotes: str, text: str | None = PAGE_TEXT, **extra: object) -> CitedSource:
    return CitedSource(url=PAGE_URL, quotes=list(quotes), text=text, grade="B", **extra)


def test_quotes_found_verbatim_in_the_fetched_page_pass() -> None:
    outcome = quote_gate(STATEMENT, [cited(QUOTE, SECOND_QUOTE)])
    assert (outcome.gate, outcome.passed) == ("QUOTES", True)
    assert outcome.reasons == ["all 2 quotes were found verbatim in their fetched sources"]


def test_a_quote_with_typographic_dashes_and_line_breaks_still_matches() -> None:
    text = "The cloth is dipped in the\nvat four times — then dried."
    assert quote_gate(
        STATEMENT, [cited("The cloth is dipped in the vat four times - then dried", text=text)]
    ).passed


def test_a_quote_the_page_does_not_hold_or_a_trivial_quote_is_refused() -> None:
    outcome = quote_gate(STATEMENT, [cited("The cloth is dipped in the vat nine times", "dipped four")])
    assert not outcome.passed
    assert outcome.reasons == [
        f"quote 1 from {PAGE_URL} is not in the page as fetched",
        f"quote 2 from {PAGE_URL} is shorter than 20 characters",
    ]


def test_an_unread_page_refuses_its_quotes_with_the_reason() -> None:
    outcome = quote_gate(STATEMENT, [cited(QUOTE, text=None, unread="Fetch refused (ROBOTS_DISALLOWED)")])
    assert outcome.reasons == [f"{PAGE_URL} could not be read: Fetch refused (ROBOTS_DISALLOWED)"]


def test_a_figure_in_the_statement_must_appear_in_a_quote() -> None:
    statement = "Ajrakh cloth is dipped in the indigo vat four times over 12 days."
    outcome = quote_gate(statement, [cited(QUOTE)])
    assert not outcome.passed
    assert outcome.reasons == ["12 in the statement appears in none of its quotes"]


def test_no_quote_at_all_passes_as_a_hypothesis() -> None:
    outcome = quote_gate("Ajrakh printers may once have used other mordants.", [cited()])
    assert outcome.passed
    assert "hypothesis" in outcome.reasons[0]


def test_a_graded_source_with_no_contradiction_passes_and_names_its_grade() -> None:
    outcome = source_gate(STATEMENT, "PROCESS", [cited(QUOTE, declared_licence="CC BY 4.0")])
    assert outcome.passed
    assert outcome.reasons == [f"{PAGE_URL} is graded B; licence: CC BY 4.0"]


def test_facts_resting_only_on_d_sources_are_refused_except_a_dated_price() -> None:
    weak = CitedSource(url=PAGE_URL, quotes=[QUOTE], text=PAGE_TEXT, grade="D")
    assert not source_gate(STATEMENT, "PROCESS", [weak]).passed
    price = "A metre of Ajrakh sold for Rs 450 at Dhamadka in 2024."
    assert source_gate(price, "ECONOMICS", [weak]).passed
    assert not source_gate(price, "HISTORY", [weak]).passed
    strong = CitedSource(url="https://other.example.org/a", quotes=[QUOTE], text=PAGE_TEXT, grade="A")
    assert source_gate(STATEMENT, "PROCESS", [weak, strong]).passed


@pytest.mark.parametrize(
    ("extra", "problem"),
    [
        ({"grade": None}, f"{PAGE_URL} has no grade"),
        ({"restricted": True}, f"{PAGE_URL} is a restricted source, whose words are never published"),
        (
            {"declared_licence": "CC BY 4.0", "stated_licence": "All rights reserved"},
            f"{PAGE_URL} is declared 'CC BY 4.0' but the page itself states 'All rights reserved'",
        ),
    ],
)
def test_an_ungraded_restricted_or_falsely_licensed_source_is_refused(extra: dict, problem: str) -> None:
    source = CitedSource(url=PAGE_URL, quotes=[QUOTE], text=PAGE_TEXT, **({"grade": "B"} | extra))
    outcome = source_gate(STATEMENT, "PROCESS", [source])
    assert (outcome.passed, outcome.reasons) == (False, [problem])


def test_a_closed_licence_the_page_states_is_allowed_when_none_is_claimed_open() -> None:
    source = cited(QUOTE, declared_licence="All rights reserved", stated_licence="All rights reserved")
    assert source_gate(STATEMENT, "PROCESS", [source]).passed


def test_the_same_statement_differently_cased_and_stopped_is_a_twin() -> None:
    same = held(
        "same", "ajrakh cloth is dipped in the indigo vat four times, the colour deepening with each dip", 0.5
    )
    assert held_twin(STATEMENT, [held("other", "Ajrakh is printed in Dhamadka.", 0.9), same]) == same
    assert held_twin(STATEMENT, [held("other", "Ajrakh is printed in Dhamadka.", 0.9)]) is None


def test_close_facts_keep_the_eight_nearest_at_or_above_the_floor() -> None:
    facts = [held(f"f{index}", f"fact {index}", 0.99 - index * 0.02) for index in range(12)]
    kept = close_facts([*reversed(facts), held("far", "far", 0.79)])
    assert [fact.id for fact in kept] == [fact_id(f"f{index}") for index in range(8)]
    assert all(fact.similarity >= 0.8 for fact in kept)


def test_a_held_twin_is_refused_without_asking_the_judge() -> None:
    twin = held("twin", STATEMENT, 1.0)
    outcome = duplicate_outcome(CANDIDATE, twin=twin, close=[], comparisons=None)
    assert (outcome.passed, outcome.related) == (False, [twin.id])


def test_a_judged_same_fact_is_refused_and_a_differing_one_is_kept_as_sources_differ() -> None:
    near, other = (
        held("near", "Ajrakh is dipped four times.", 0.93),
        held("other", "Ajrakh dips thrice.", 0.88),
    )
    same = FactComparison(held=near.id, relation="SAME", reason="Both say four dips.")
    refused = duplicate_outcome(CANDIDATE, twin=None, close=[near], comparisons=[same], model="m")
    assert (refused.passed, refused.related, refused.model) == (False, [near.id], "m")
    differs = FactComparison(held=other.id, relation="DIFFERS", reason="Three dips against four.")
    distinct = FactComparison(held=near.id, relation="DISTINCT", reason="One is about lime.")
    kept = duplicate_outcome(CANDIDATE, twin=None, close=[near, other], comparisons=[distinct, differs])
    assert (kept.passed, kept.related) == (True, [other.id])
    assert (
        kept.reasons[1]
        == f"it differs from fact {other.id}, kept as sources differ: Three dips against four."
    )
    assert (refused.about, kept.about) == (None, None)


def test_the_duplicate_gate_names_what_the_first_named_differing_fact_differs_on() -> None:
    near, other = (
        held("near", "Ajrakh is dipped four times.", 0.93),
        held("other", "Ajrakh dips five times.", 0.9),
    )
    unnamed = FactComparison(held=near.id, relation="DIFFERS", reason="Three dips against four.")
    named = FactComparison(
        held=other.id,
        relation="DIFFERS",
        reason="Three dips against five.",
        about="The indigo vat, number of dips",
    )
    kept = duplicate_outcome(CANDIDATE, twin=None, close=[near, other], comparisons=[unnamed, named])
    assert (kept.passed, kept.related, kept.about) == (
        True,
        [near.id, other.id],
        "The indigo vat, number of dips",
    )


def test_without_close_facts_vectors_or_a_judge_the_duplicate_gate_says_what_it_did() -> None:
    lone = duplicate_outcome(CANDIDATE, twin=None, close=[], comparisons=None)
    assert lone.reasons == ["no held fact of this subject in PROCESS is close to it"]
    unjudged = duplicate_outcome(CANDIDATE, twin=None, close=[held("n", "x", 0.9)], comparisons=None)
    assert unjudged.passed and "no judge compared them" in unjudged.reasons[0]
    blind = duplicate_outcome(CANDIDATE, twin=None, close=[], comparisons=None, vectored=False)
    assert blind.passed and blind.reasons[0].startswith("only identical texts were looked for")


def test_novelty_passes_a_differing_fact_and_a_first_fact_without_the_judge() -> None:
    other = fact_id("other")
    differ = novelty_outcome(CANDIDATE, differs=[other], held_count=4, verdict=None)
    assert differ is not None and (differ.passed, differ.related) == (True, [other])
    first = novelty_outcome(CANDIDATE, differs=[], held_count=0, verdict=None)
    assert first is not None and first.reasons == [
        "the subject holds no fact in PROCESS yet, so it adds to the section"
    ]
    assert novelty_outcome(CANDIDATE, differs=[], held_count=3, verdict=None) is None


def test_the_judge_s_novelty_verdict_decides_and_a_refusal_names_the_covering_facts() -> None:
    covering = fact_id("covering")
    trivial = NoveltyVerdict(adds=False, covered_by=[covering], reason="The section already says it.")
    refused = novelty_outcome(CANDIDATE, differs=[], held_count=3, verdict=trivial, model="m")
    assert refused is not None and (refused.passed, refused.related, refused.model) == (
        False,
        [covering],
        "m",
    )
    adds = NoveltyVerdict(adds=True, covered_by=[covering], reason="It gives the number of dips.")
    kept = novelty_outcome(CANDIDATE, differs=[], held_count=3, verdict=adds)
    assert kept is not None and (kept.passed, kept.related) == (True, [])
