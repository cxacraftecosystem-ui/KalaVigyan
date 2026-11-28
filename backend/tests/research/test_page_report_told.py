from typing import Any

from app.research.coverage import CoverageSubject, Holdings, field_coverage
from app.research.monograph_document import MonographDocument
from app.research.page_report import ReportInput, page_report
from app.research.page_report_read import ReadPage
from app.research.page_report_rules import checked_rules

from .page_report_rules_fixtures import FIGURE, page_document, plain, sentence

HILLS = "The hills round the town are fractured quartzite of the fold belt."
VALLEYS = "Alluvium up to 100 m thick fills the valleys between the hills."
SOIL = "The sandy soil lets the wastewater sink into the groundwater."
BLOCK = "test-craft/blocks/made-ladder"
GAP_UNIT = "chemistry-6"
GAP_TEXT = "Its dye chemistry is not yet researched by anyone."
FACT = "0e000000-0000-4000-8000-0000000000c8"


def held_by(document: MonographDocument, refs: set[str], label: str = FIGURE) -> MonographDocument:
    body = document.model_dump(mode="json", by_alias=True)
    for entry in body["content"]["layout"]:
        if entry["ref"] in refs:
            entry["within"] = label
    return MonographDocument.model_validate(body)


def geology(*texts: str) -> dict[str, dict[str, Any]]:
    return {f"geology-{at}": sentence("GEOLOGY", text, f"g{at}") for at, text in enumerate(texts, start=1)}


def evidence(document: MonographDocument, rule: int) -> list[str]:
    return checked_rules(ReportInput(document=document))[rule][1]


def standing(document: MonographDocument, field: str) -> tuple[int, str]:
    lines = {line.field: line for line in page_report(ReportInput(document=document), {}).fields}
    return lines[field].sentences, lines[field].standing


def test_a_field_whose_sentences_its_figure_holds_is_dense_as_the_page_draws_it() -> None:
    document = held_by(page_document(extra=geology(HILLS, VALLEYS, SOIL)), {"geology-2", "geology-3"})
    page = ReadPage.of(document)
    assert (page.by_field()["GEOLOGY"], page.told_by_field()["GEOLOGY"]) == (1, 3)
    assert not [line for line in evidence(document, 24) if line.startswith("GEOLOGY")]
    assert standing(document, "GEOLOGY") == (3, "DENSE")


def test_a_field_told_only_in_a_figure_has_its_sentence_on_the_page_and_one_told_nowhere_has_none() -> None:
    holdings = Holdings(filed={"g1": frozenset({"GEOLOGY"})}, sources={"g1": frozenset({"s1"})})
    coverage = field_coverage(CoverageSubject("craft", "Test-Craft", "Test craft"), holdings, claims_min=3)
    covered = coverage.model_dump(by_alias=True)
    figured = held_by(page_document(extra=geology(HILLS), coverage=covered), {"geology-1"})
    assert not [line for line in evidence(figured, 23) if line.startswith("GEOLOGY holds")]
    assert "GEOLOGY holds 1 facts but no sentence on the page" in evidence(
        page_document(coverage=covered), 23
    )


def test_a_field_told_once_stays_thin_and_a_figure_s_label_or_its_retold_prose_adds_nothing() -> None:
    extra = {**geology(HILLS), "geology-2": sentence("GEOLOGY", "Quartzite hills", "g2")}
    extra["geology-3"] = sentence("GEOLOGY", HILLS, "g1")
    document = held_by(page_document(extra=extra), {"geology-2", "geology-3"})
    assert "GEOLOGY has 1 sentences" in evidence(document, 24)
    assert standing(document, "GEOLOGY") == (1, "THIN")


def block_document(*, cited: bool) -> MonographDocument:
    body = page_document().model_dump(mode="json", by_alias=True)
    content = body["content"]
    figure = next(component for component in content["components"] if component["label"] == FIGURE)
    stage = {"field": "PROCESS", "chapter": "made"}
    content["components"].append({**figure, **stage, "label": BLOCK, "kind": "answer_block"})
    content["layout"].append({"chapter": "made", "kind": "component", "ref": BLOCK, "within": None})
    citations = [{"claimId": "c5", "sourceId": "s1", "quote": "dipped"}] if cited else []
    stages = [
        {"name": "Dipping", "sentences": [{"text": text, "citations": citations}]}
        for text in ("The cloth is lowered into the vat.", "The cloth is lifted out green.")
    ]
    body["specs"][BLOCK] = {"block": {"kind": "process_ladder", "stages": stages}}
    return MonographDocument.model_validate(body)


def test_a_structure_block_s_cited_sentences_count_for_its_field_and_uncited_ones_do_not() -> None:
    assert not [line for line in evidence(block_document(cited=True), 24) if line.startswith("PROCESS")]
    assert standing(block_document(cited=True), "PROCESS") == (3, "DENSE")
    assert "PROCESS has 1 sentences" in evidence(block_document(cited=False), 24)


def test_a_figure_unit_repeating_the_prose_names_its_figure_and_the_sentence_it_repeats() -> None:
    extra = {"chemistry-4": sentence("CHEMISTRY", "The madder bath turns the alum print red.", "c3")}
    document = held_by(page_document(extra=extra), {"chemistry-4"})
    assert evidence(document, 25) == [
        f"chemistry-4 in {FIGURE} repeats chemistry-2: 'The madder bath turns the alum print red.'"
    ]
    assert checked_rules(ReportInput(document=page_document()))[25][0] == "PASS"


def test_a_fact_that_reads_as_a_gap_names_its_fact_and_the_tools_that_fix_it() -> None:
    gap = {GAP_UNIT: sentence("CHEMISTRY", GAP_TEXT, FACT)}
    assert evidence(page_document(extra=gap), 26) == [
        f"'{GAP_TEXT}' reads as a gap: {GAP_UNIT} draws fact {FACT}; propose_facts a fact of CHEMISTRY "
        f"stating what its source does find, and an Admin retracts fact {FACT} with stage_reviews "
        "(kind FACTS, action retract)"
    ]
    assert checked_rules(ReportInput(document=page_document()))[26][0] == "PASS"


def test_a_unit_of_the_page_s_own_that_admits_a_gap_names_its_figure_and_edit_draft() -> None:
    own = {"u5002": plain("chem", "span", "No data on this colour")}
    document = held_by(page_document(extra=own), {"u5002"})
    assert evidence(document, 26) == [
        f"'No data on this colour' admits a gap: edit_draft: remove u5002 in {FIGURE} and add it back saying "
        "what its facts state"
    ]
