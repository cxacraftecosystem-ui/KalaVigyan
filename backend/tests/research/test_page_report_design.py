from typing import Any

from app.research.page_report import ReportInput
from app.research.page_report_design import DESIGN_RULE, delivered, design_evidence
from app.research.page_report_rules import checked_rules

from .page_report_rules_fixtures import FIGURE, PICTURE, page_document

THEMED = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 200"><rect fill="#1C1815"/></svg>'
ROLES = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 200"><rect fill="var(--ink-1)"/></svg>'
FOUR = {"light": THEMED, "dark": THEMED, "hcLight": THEMED, "hcDark": THEMED}
TEXTS = {"u5003": "Two rings of clay around the wax", "u0003": "An authored drawing"}


def evidence_for(
    specs: dict[str, dict[str, Any]], held: dict[str, list[str]], pictures: list[str]
) -> list[str]:
    figures = [(label, "drawing") for label in specs if label not in pictures]
    return design_evidence(
        figures, specs, lambda label: held.get(label, []), lambda unit: TEXTS.get(unit, ""), pictures
    )


def test_a_delivered_unit_is_one_the_page_renamed_into_the_delivery_range() -> None:
    assert delivered(["u0001", "u5001"]) and delivered(["u8999"])
    assert not delivered(["u0001", "u4999", "u9001", "cite"])


def test_a_delivered_drawing_in_roles_and_four_themes_with_its_alt_text_passes() -> None:
    spec = {"head": {"title": "u5001"}, "svg": ROLES, "alt": "u5003", "themes": FOUR}
    assert evidence_for({"a/b/drawing": spec}, {"a/b/drawing": ["u5001", "u5003"]}, []) == []


def test_a_delivered_drawing_without_its_themes_its_alt_or_its_roles_fails_with_the_evidence() -> None:
    spec = {"head": {"title": "u5001"}, "svg": THEMED, "alt": "u5009", "themes": {"light": THEMED}}
    found = evidence_for({"a/b/drawing": spec}, {"a/b/drawing": ["u5001"]}, [])
    assert found[0].startswith("a/b/drawing: a <rect>'s fill names the colour '#1C1815'")
    assert found[1:] == [
        "a/b/drawing is a drawing without its light, dark and high-contrast variants",
        "a/b/drawing is a drawing with no alt text saying what it shows",
    ]


def test_an_authored_figure_is_left_to_its_own_page_and_a_picture_without_alt_text_fails() -> None:
    authored = {"head": {"title": "u0001"}, "svg": THEMED, "alt": "u0003"}
    specs = {"a/b/authored": authored, "a/b/plate": {"picture": {"src": "/x", "alt": " "}}}
    found = evidence_for(specs, {"a/b/authored": ["u0001"]}, ["a/b/plate"])
    assert found == ["a/b/plate has no alt text saying what the picture shows"]


def test_the_checklist_reports_the_design_rule_and_fails_a_delivered_off_vocabulary_figure() -> None:
    document = page_document()
    assert checked_rules(ReportInput(document=document))[DESIGN_RULE][0] == "PASS"
    specs = {
        **document.specs,
        FIGURE: {"head": {"title": "u5001"}, "drawing": {"tag": "rect", "attrs": {"fill": "red"}}},
    }
    off = document.model_copy(update={"specs": specs})
    verdict, found = checked_rules(ReportInput(document=off))[DESIGN_RULE]
    assert verdict == "FAIL" and found[0].startswith(f"{FIGURE}: a <rect>'s fill names the colour 'red'")
    assert PICTURE in document.specs
