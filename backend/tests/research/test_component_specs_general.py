from typing import Any

import pytest
from pydantic import ValidationError

from app.models.component_kinds import GENERAL_KINDS, PIECE_KINDS
from app.research.component_specs import SPEC_MODELS, checked_spec
from app.research.component_specs_general import SPEC_MODELS_GENERAL
from app.research.component_specs_general_svg import cleaned_svg, drawing_tags, svg_view_box

from .general_spec_fixtures import CHART, DRAWING, MAP_LAYER, SVG, TABLE, TIMELINE

SAMPLES = {
    "general_drawing": DRAWING,
    "general_chart": CHART,
    "general_table": TABLE,
    "general_timeline": TIMELINE,
    "general_map_layer": MAP_LAYER,
}
SVG_OPEN = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'


def test_the_five_general_kinds_are_piece_kinds_with_a_spec_model_each() -> None:
    assert set(SPEC_MODELS_GENERAL) == set(GENERAL_KINDS) == set(SAMPLES)
    assert set(GENERAL_KINDS) <= set(PIECE_KINDS)
    assert all(SPEC_MODELS[kind] is SPEC_MODELS_GENERAL[kind] for kind in GENERAL_KINDS)


@pytest.mark.parametrize("kind", GENERAL_KINDS)
def test_each_general_kind_validates_its_sample(kind: str) -> None:
    checked_spec(kind, SAMPLES[kind])


@pytest.mark.parametrize(
    ("kind", "changes", "says"),
    [
        ("general_chart", {"form": "pie"}, "form"),
        ("general_chart", {"emphasis": 5}, "emphasised point"),
        ("general_chart", {"series": [*CHART["series"], {"name": "u0009", "points": []}]}, "at least 1"),
        (
            "general_chart",
            {"series": [{"name": "u0004", "points": [{"label": "u0005", "value": -3, "reading": "u0006"}]}]},
            "no negative value",
        ),
        ("general_table", {"rows": [{"cells": ["u0005"]}]}, "one cell per column"),
        ("general_timeline", {"events": list(reversed(TIMELINE["events"]))}, "order of their years"),
        (
            "general_map_layer",
            {"places": [{**MAP_LAYER["places"][0], "longitude": 101.5}]},
            "less than or equal",
        ),
        ("general_map_layer", {"valueLabel": None}, "valueLabel"),
        ("general_drawing", {"svg": "<div>not a drawing</div>"}, "svg element"),
    ],
)
def test_a_general_spec_off_its_rules_is_refused(kind: str, changes: dict[str, Any], says: str) -> None:
    with pytest.raises(ValidationError, match=says):
        checked_spec(kind, {**SAMPLES[kind], **changes})


def test_a_line_joins_at_least_two_points() -> None:
    one = {"name": "u0004", "points": [{"label": "u0005", "value": 3, "reading": "u0006"}]}
    with pytest.raises(ValidationError, match="two points"):
        checked_spec("general_chart", {**CHART, "form": "line", "series": [one], "emphasis": None})


def test_a_drawing_keeps_its_shapes_and_drops_its_fixed_size() -> None:
    cleaned = checked_spec("general_drawing", DRAWING).model_dump(mode="json")["svg"]
    assert cleaned == (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 60">'
        '<rect x="1" y="1" width="20" height="10" fill="#1C1815" /></svg>'
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
        "<circle style='fill: red' r='1'/><circle style='behaviour: url(evil.htc)' r='2'/></svg>"
    )
    assert cleaned_svg(markup) == (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="3" />'
        '<use href="#mark" /><use /><circle style="fill: red" r="1" /><circle r="2" /></svg>'
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
