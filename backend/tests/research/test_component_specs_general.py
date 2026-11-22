from typing import Any

import pytest
from pydantic import ValidationError

from app.models.component_kinds import GENERAL_KINDS, PIECE_KINDS
from app.research.component_specs import SPEC_MODELS, checked_spec
from app.research.component_specs_data import ChartSpec, FactTableSpec
from app.research.component_specs_either import EITHER_FORMS
from app.research.component_specs_general import DECLARED_SPEC_MODELS, SPEC_MODELS_GENERAL, GeneralTableSpec
from app.research.component_specs_general_svg import cleaned_svg, drawing_tags, svg_view_box

from .general_spec_fixtures import CHART, DRAWING, MAP_LAYER, SVG, TABLE, TIMELINE

SAMPLES = {
    "drawing": DRAWING,
    "chart": CHART,
    "fact_table": TABLE,
    "timeline": TIMELINE,
    "map_layer": MAP_LAYER,
}
AUTHORED_TABLE = {
    "id": "glance",
    "numeral": 1,
    "chapterNo": "u0001",
    "title": "u0002",
    "titleId": "glance-t",
    "rows": [{"term": "u0003", "value": "u0004"}],
}
SVG_OPEN = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'


def test_the_five_kinds_with_a_declared_form_are_piece_kinds_and_no_general_name_is_left() -> None:
    assert set(GENERAL_KINDS) == set(SAMPLES) == {"drawing", "chart", "fact_table", "timeline", "map_layer"}
    assert set(GENERAL_KINDS) <= set(PIECE_KINDS)
    assert set(SPEC_MODELS_GENERAL) | set(DECLARED_SPEC_MODELS) == set(GENERAL_KINDS)
    assert not [kind for kind in (*PIECE_KINDS, *SPEC_MODELS) if kind.startswith("general_")]


def test_one_kind_per_job_takes_the_declared_and_the_authored_spec() -> None:
    assert set(EITHER_FORMS) == {"chart", "fact_table", "timeline", "map_layer"}
    assert isinstance(checked_spec("fact_table", TABLE), GeneralTableSpec)
    assert isinstance(checked_spec("fact_table", AUTHORED_TABLE), FactTableSpec)
    assert EITHER_FORMS["chart"]["authored"] is ChartSpec
    assert SPEC_MODELS["drawing"] is SPEC_MODELS_GENERAL["drawing"]


def test_an_authored_spec_off_its_model_is_refused_by_the_authored_model() -> None:
    with pytest.raises(ValidationError, match="rows"):
        checked_spec("fact_table", {**AUTHORED_TABLE, "rows": []})


@pytest.mark.parametrize("kind", GENERAL_KINDS)
def test_each_general_kind_validates_its_sample(kind: str) -> None:
    checked_spec(kind, SAMPLES[kind])


@pytest.mark.parametrize(
    ("kind", "changes", "says"),
    [
        ("chart", {"form": "pie"}, "form"),
        ("chart", {"emphasis": 5}, "emphasised point"),
        ("chart", {"series": [*CHART["series"], {"name": "u0009", "points": []}]}, "at least 1"),
        (
            "chart",
            {"series": [{"name": "u0004", "points": [{"label": "u0005", "value": -3, "reading": "u0006"}]}]},
            "no negative value",
        ),
        ("fact_table", {"rows": [{"cells": ["u0005"]}]}, "one cell per column"),
        ("timeline", {"events": list(reversed(TIMELINE["events"]))}, "order of their years"),
        (
            "map_layer",
            {"places": [{**MAP_LAYER["places"][0], "longitude": 101.5}]},
            "less than or equal",
        ),
        ("map_layer", {"valueLabel": None}, "valueLabel"),
        ("drawing", {"svg": "<div>not a drawing</div>"}, "svg element"),
    ],
)
def test_a_general_spec_off_its_rules_is_refused(kind: str, changes: dict[str, Any], says: str) -> None:
    with pytest.raises(ValidationError, match=says):
        checked_spec(kind, {**SAMPLES[kind], **changes})


def test_a_line_joins_at_least_two_points() -> None:
    one = {"name": "u0004", "points": [{"label": "u0005", "value": 3, "reading": "u0006"}]}
    with pytest.raises(ValidationError, match="two points"):
        checked_spec("chart", {**CHART, "form": "line", "series": [one], "emphasis": None})


def test_a_drawing_keeps_its_shapes_and_drops_its_fixed_size() -> None:
    cleaned = checked_spec("drawing", DRAWING).model_dump(mode="json")["svg"]
    assert cleaned == (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 60">'
        '<rect x="1" y="1" width="20" height="10" fill="var(--ink-1)" /></svg>'
    )
    assert cleaned != SVG


@pytest.mark.parametrize(
    ("inner", "kept"),
    [
        ("<script>alert(1)</script><circle r='2'/>", ["svg", "circle"]),
        (
            "<foreignObject><div xmlns='http://www.w3.org/1999/xhtml'>x</div></foreignObject><g/>",
            ["svg", "g"],
        ),
        ("<image href='https://example.org/a.png'/><path d='M0 0'/>", ["svg", "path"]),
        ("<style>@import url(https://example.org/x.css);</style><line x2='4'/>", ["svg", "line"]),
    ],
)
def test_scripts_foreign_objects_images_and_styles_are_removed(inner: str, kept: list[str]) -> None:
    assert list(drawing_tags(cleaned_svg(f"{SVG_OPEN}{inner}</svg>"))) == kept


def test_event_handlers_and_outside_references_are_removed_and_local_ones_kept() -> None:
    markup = (
        f"{SVG_OPEN}<rect onclick='steal()' onload='x()' fill='url(https://example.org/p)' width='3'/>"
        "<use href='#mark'/><use href='https://example.org/s.svg#mark'/>"
        "<circle style='fill: var(--ink-2)' r='1'/><circle style='behaviour: url(evil.htc)' r='2'/></svg>"
    )
    assert cleaned_svg(markup) == (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="3" />'
        '<use href="#mark" /><use /><circle style="fill: var(--ink-2)" r="1" /><circle r="2" /></svg>'
    )


@pytest.mark.parametrize(
    ("markup", "says"),
    [
        ('<!DOCTYPE svg [<!ENTITY a "x">]><svg viewBox="0 0 1 1"/>', "document type"),
        (
            '<?xml-stylesheet href="x.css"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>',
            "processing",
        ),
        ('<svg xmlns="http://www.w3.org/2000/svg"><g/></svg>', "viewBox"),
        ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 0 5"/>', "viewBox"),
        ("<svg viewBox='0 0 1 1'/>", "SVG namespace"),
        ("<svg", "well-formed"),
    ],
)
def test_a_drawing_that_is_not_one_plain_svg_is_refused(markup: str, says: str) -> None:
    with pytest.raises(ValueError, match=says):
        cleaned_svg(markup)


def test_a_drawing_has_a_size_limit() -> None:
    with pytest.raises(ValueError, match="at most 200000"):
        cleaned_svg(SVG_OPEN + "<g/>" * 50_000 + "</svg>")


def test_a_view_box_is_four_numbers_with_a_positive_size() -> None:
    assert svg_view_box("0 0 120 60") == (0.0, 0.0, 120.0, 60.0)
    assert svg_view_box("-5,-5 10 10") == (-5.0, -5.0, 10.0, 10.0)
    assert svg_view_box("0 0 120") is None
    assert svg_view_box(None) is None
