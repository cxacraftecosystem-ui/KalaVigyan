import uuid
from typing import Any

import pytest

from app.research.coverage import CoverageSubject, Holdings, field_coverage
from app.research.monograph_document import MonographDocument
from app.research.page_drafts import PageLists
from app.research.page_report import ReportInput, page_report, picture_licence
from app.research.page_report_rules import checked_rules
from app.research.structure_proposals import ReactionItem
from app.services.monograph_generated_units import MASTHEAD_CHAPTER
from app.services.page_report import checklist_titles

from .page_report_rules_fixtures import (
    FIGURE,
    PICTURE,
    STATEMENT,
    page_document,
    sentence,
)

LISTS = PageLists(mechanisms=["alum", "indigo"], ambiguous_terms=["lime"], signature="fact:0")
REACTION = ReactionItem.model_validate(
    {
        "reactionKind": "COMPLEXATION",
        "reactants": [{"name": "alum", "formula": "KAl(SO4)2"}],
        "products": [{"name": "aluminium hydroxide", "formula": "Al(OH)3"}],
    }
)
SUPPLIED = {"https://example.org/madder": "B"}


def given(document: MonographDocument, **changes: Any) -> ReportInput:
    base: dict[str, Any] = {
        "document": document,
        "lists": LISTS,
        "statements": {"fact:0": STATEMENT},
        "reactions": (REACTION,),
        "supplied": SUPPLIED,
    }
    return ReportInput(**(base | changes))


def verdicts(report_input: ReportInput) -> dict[int, str]:
    return {number: verdict for number, (verdict, _) in checked_rules(report_input).items()}


def evidence(report_input: ReportInput, rule: int) -> list[str]:
    return checked_rules(report_input)[rule][1]


def test_the_opening_chapter_is_the_generated_document_s_masthead() -> None:
    assert MASTHEAD_CHAPTER == "opening"


def test_every_rule_is_reported_and_the_machine_checks_give_their_verdicts() -> None:
    found = verdicts(given(page_document()))
    assert sorted(found) == list(range(1, 27))
    assert [n for n, v in found.items() if v == "FAIL"] == [4, 20, 21, 23, 24]
    assert [n for n, v in found.items() if v == "PASS"] == [1, 2, 3, 6, 7, 9, 10, 14, 15, 17, 25, 26]
    assert [n for n, v in found.items() if v == "JUDGE"] == [5, 8, 11, 12, 13, 16, 18, 19, 22]


def test_each_failure_names_its_evidence() -> None:
    report_input = given(page_document())
    assert evidence(report_input, 4) == ["chemistry-1 states 70, which no quote it cites holds"]
    assert evidence(report_input, 20) == ["'indigo' is told in 0 sentences"]
    assert evidence(report_input, 21) == ["alum loses or gains H, K, S"]
    assert evidence(report_input, 23) == ["process-1 (PROCESS) sits in chem, not made"]
    assert evidence(report_input, 24) == ["OVERVIEW has 1 sentences", "PROCESS has 1 sentences"]
    assert evidence(report_input, 18) == ["'lime' is used in 0 sentences"]
    assert evidence(report_input, 6) == ["the signature fact is told once, in chemistry-1"]


def test_without_the_page_s_lists_their_rules_are_left_to_judge() -> None:
    found = verdicts(given(page_document(), lists=None, reactions=()))
    assert (found[6], found[18], found[20], found[21]) == ("JUDGE", "JUDGE", "JUDGE", "JUDGE")


def test_a_field_holding_facts_without_a_sentence_fails_rule_23() -> None:
    holdings = Holdings(filed={"c9": frozenset({"HISTORY"})}, sources={"c9": frozenset({"s1"})})
    coverage = field_coverage(CoverageSubject("craft", "Test-Craft", "Test craft"), holdings, claims_min=3)
    report_input = given(page_document(coverage=coverage.model_dump(by_alias=True)))
    assert "HISTORY holds 1 facts but no sentence on the page" in evidence(report_input, 23)


def test_a_repeated_sentence_a_progress_state_and_an_admitted_gap_fail() -> None:
    extra = {
        "chemistry-4": sentence("CHEMISTRY", "The madder bath turns the alum print red.", "c6"),
        "chemistry-5": sentence("CHEMISTRY", "Writing section 2 of 5 for the madder chapter now.", "c7"),
        "chemistry-6": sentence("CHEMISTRY", "Its dye chemistry is not yet researched by anyone.", "c8"),
    }
    found = verdicts(given(page_document(extra=extra)))
    assert (found[10], found[25], found[26]) == ("FAIL", "FAIL", "FAIL")
    assert evidence(given(page_document(extra=extra)), 25) == [
        "'The madder bath turns the alum print red.' is told twice"
    ]


def test_a_long_lede_a_question_title_and_a_second_masthead_picture_fail() -> None:
    lede = {
        f"overview-{n}": sentence("OVERVIEW", f"Test craft is printed in {n} towns.", f"o{n}", "opening")
        for n in (2, 3, 4)
    }
    document = page_document(extra=lede, chapter=dict.fromkeys(lede, "opening"), title="Why is it red?")
    report_input = given(document)
    assert evidence(report_input, 1) == [
        "'Why is it red?' is a question; state the finding",
        "the lede holds 4 sentences; keep it to 3",
    ]
    second = page_document(second_picture=True)
    assert verdicts(given(second))[3] == "FAIL" and verdicts(given(second))[7] == "FAIL"


def test_a_signature_told_twice_or_missing_fails_and_a_category_masthead_is_judged() -> None:
    claim = uuid.UUID("0e000000-0000-4000-8000-0000000000c2")
    twice = page_document(
        extra={"chemistry-4": sentence("CHEMISTRY", "Alum is the mordant of the red.", str(claim))}
    )
    told = evidence(given(twice, lists=PageLists(signature=claim)), 6)
    assert told == ["the signature fact is told 2 times (chemistry-1, chemistry-4); tell it once"]
    missing = evidence(given(page_document(), lists=PageLists(signature="fact:0"), statements={}), 6)
    assert missing == ["the signature fact fact:0 is on no sentence of the page"]
    assert verdicts(given(page_document(subject_kind="category")))[2] == "JUDGE"


def test_the_report_counts_fields_figures_sources_and_pictures() -> None:
    report = page_report(given(page_document()), {4: "One count, and it is true"})
    assert (report.passed, report.failed, report.judged) == (12, 5, 9)
    assert report.rules[3].title == "One count, and it is true" and report.rules[0].title == "Rule 1"
    lines = {line.field: (line.sentences, line.figures, line.standing) for line in report.fields}
    assert lines["CHEMISTRY"] == (3, 1, "DENSE")
    assert lines["OVERVIEW"] == (1, 0, "THIN") and lines["HISTORY"] == (0, 0, "ABSENT")
    assert [(f.number, f.label, f.cited) for f in report.figures] == [(1, FIGURE, True)]
    assert report.figure_kinds == {"general_table": 1}
    assert (report.sources, report.sources_by_grade, report.supplied_sources) == (2, {"A": 1, "B": 1}, 1)
    assert [(p.label, p.licence) for p in report.pictures] == [(PICTURE, "CC BY-SA 4.0")]
    assert (report.sentences, report.lede_sentences) == (5, 1)


@pytest.mark.parametrize(
    ("credit", "licence"),
    [
        ("Contributed to KalaVigyan", "CONTRIBUTED"),
        ("Illustration, made with Imagen 4", "AI_ILLUSTRATION"),
        ("Photo: A. Rao, public domain, via Wikimedia Commons", "Public domain"),
        ("Photo: A. Rao, cc-by 4.0, via Wikimedia Commons", "CC BY 4.0"),
        ("Photo: A. Rao, CC0, via Wikimedia Commons", "CC0"),
        ("Photo: Wikimedia Commons", "NAMED_IN_CREDIT"),
    ],
)
def test_a_picture_s_licence_is_read_from_its_credit(credit: str, licence: str) -> None:
    assert picture_licence(credit) == licence


def test_the_rule_titles_come_from_the_checklist_reference() -> None:
    titles = checklist_titles()
    assert sorted(titles) == list(range(1, 27))
    assert titles[1] == "A short headline, never a raw question"
    assert titles[4] == "One count, and it is true"
    assert titles[26] == "A missing field is research, not a hole"
