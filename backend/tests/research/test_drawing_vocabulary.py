import pytest
from pydantic import ValidationError

from app.core.errors import InvalidInput
from app.research.component_specs import checked_spec
from app.research.component_specs_general_svg import cleaned_svg
from app.research.drawing_roles import DRAWING_ROLES, paint_problem, role_problem
from app.research.drawing_spec_rules import spec_design_problems
from app.research.image_intake_svg import clean_svg

from .general_spec_fixtures import DRAWING

OPEN = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 320">'
TEXT_AT_FLOOR = 24


def drawing(inner: str) -> str:
    return f"{OPEN}{inner}</svg>"


def refusal(markup: str) -> str:
    with pytest.raises(ValueError) as wrong:
        cleaned_svg(markup)
    return str(wrong.value)


def test_a_drawing_in_design_roles_is_kept_as_it_was_given() -> None:
    markup = drawing(
        '<rect width="640" height="320" fill="var(--sunk)"/>'
        '<path d="M0 0L640 320" stroke="color-mix(in srgb, var(--ink-1) 40%, var(--ground))"/>'
        f'<text x="8" y="40" font-size="{TEXT_AT_FLOOR}" fill="var(--ink-2)">Alum</text>'
        '<circle r="9" fill="var(--dye-madder)" stroke="var(--map-coast)"/>'
        '<rect width="9" height="9" fill="var(--rain-3)" stroke="currentColor"/>'
    )
    assert "var(--dye-madder)" in cleaned_svg(markup)


@pytest.mark.parametrize(
    ("paint", "says"),
    [
        ("#1C1815", "'#1C1815'"),
        ("rgb(28, 24, 21)", "'rgb(28, 24, 21)'"),
        ("hsl(20 10% 10%)", "'hsl(20 10% 10%)'"),
        ("rebeccapurple", "'rebeccapurple'"),
        ("var(--indigo)", "indigo, which means a control"),
        ("var(--turmeric)", "--turmeric is not one of the design's roles"),
        ("var(--dye-plastic)", "--dye-plastic is not a depicted material"),
    ],
)
def test_a_colour_off_the_design_s_roles_is_refused_naming_the_element_and_the_roles(
    paint: str, says: str
) -> None:
    told = refusal(drawing(f'<rect id="vat" width="9" height="9" fill="{paint}"/>'))
    assert '<rect id="vat">' in told and says in told
    assert "--ink-1 to --ink-3" in told and "--terracotta only for place" in told


def test_a_colour_in_a_style_attribute_is_held_to_the_same_roles() -> None:
    assert "'#ff0000'" in refusal(drawing('<circle r="2" style="fill:#ff0000"/>'))


def test_a_named_font_is_refused_in_an_attribute_and_in_a_style() -> None:
    assert "names a font" in refusal(drawing('<g font-family="Comic Sans MS"/>'))
    assert "names a font" in refusal(drawing(f'<text style="font: {TEXT_AT_FLOOR}px serif">a</text>'))


def test_text_under_twelve_pixels_at_the_narrowest_width_is_refused() -> None:
    told = refusal(drawing('<text font-size="16" fill="var(--ink-1)">Kachchh</text>'))
    assert "Kachchh" in told and "8.0 px" in told and f"{TEXT_AT_FLOOR} units or more" in told
    assert "Kachchh" in refusal(
        drawing(f'<g transform="scale(0.5)"><text font-size="{TEXT_AT_FLOOR}">Kachchh</text></g>')
    )
    assert cleaned_svg(drawing(f'<text font-size="{TEXT_AT_FLOOR}">Kachchh</text>'))


def test_text_with_no_size_takes_sixteen_units_and_is_held_to_the_floor() -> None:
    assert "under the 12 px floor" in refusal(drawing("<text>Bhuj</text>"))


def test_a_gradient_blending_two_roles_and_text_in_a_gradient_are_refused() -> None:
    blend = (
        '<defs><linearGradient id="g"><stop stop-color="var(--ink-1)"/><stop stop-color="var(--terracotta)"/>'
        '</linearGradient></defs><rect width="9" height="9" fill="url(#g)"/>'
    )
    assert 'the gradient "g" blends' in refusal(drawing(blend))
    fade = '<defs><linearGradient id="f"><stop stop-color="var(--ink-1)" stop-opacity="0"/><stop stop-color="var(--ink-1)"/></linearGradient></defs>'
    assert cleaned_svg(drawing(fade + f'<text font-size="{TEXT_AT_FLOOR}" fill="var(--ink-1)">a</text>'))
    told = refusal(drawing(fade + f'<text font-size="{TEXT_AT_FLOOR}" fill="url(#f)">Dip</text>'))
    assert "'Dip' is filled with a gradient" in told


def test_a_ramp_or_depicted_materials_may_share_a_gradient() -> None:
    ramp = '<defs><linearGradient id="r"><stop stop-color="var(--rain-1)"/><stop stop-color="var(--rain-6)"/></linearGradient></defs>'
    dips = '<defs><linearGradient id="d"><stop stop-color="var(--dip-1)"/><stop stop-color="var(--dye-indigo)"/></linearGradient></defs>'
    assert cleaned_svg(drawing(ramp)) and cleaned_svg(drawing(dips))


def test_words_drawn_as_outlines_are_refused() -> None:
    inkscape = '<g aria-label="Alum" style="font-size:20px"><path d="M0 0h4v4z"/></g>'
    assert "draws words as outlines" in refusal(drawing(inkscape))
    assert "draws words as outlines" in refusal(drawing('<path id="glyph0-1" d="M0 0h4"/>'))
    assert cleaned_svg(drawing('<g aria-label="The vat"><path d="M0 0h4"/></g>'))


def test_a_mask_may_paint_in_white_and_black() -> None:
    mask = '<defs><mask id="m"><rect width="9" height="9" fill="#fff"/><rect width="2" height="2" fill="black"/></mask></defs>'
    assert cleaned_svg(drawing(mask))
    assert "'#fff'" in refusal(drawing('<rect width="9" height="9" fill="#fff"/>'))


def test_a_contributed_svg_picture_is_held_to_the_same_vocabulary() -> None:
    base = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480">'
    assert clean_svg(base + b'<rect width="640" height="480" fill="var(--map-land)"/></svg>').width == 640
    with pytest.raises(InvalidInput, match="speaks only the design's vocabulary"):
        clean_svg(base + b'<rect width="640" height="480" fill="blue"/></svg>')
    blur = b'<defs><filter id="b"><feGaussianBlur stdDeviation="4"/></filter></defs><rect filter="url(#b)"/></svg>'
    with pytest.raises(InvalidInput, match="a retired look"):
        clean_svg(base + blur)
    with pytest.raises(InvalidInput, match="names a font"):
        clean_svg(base + b"<style>text { font-family: Papyrus }</style></svg>")


def test_a_drawing_spec_refuses_a_typed_colour_through_its_model() -> None:
    hexed = {**DRAWING, "svg": drawing('<rect width="9" height="9" fill="#123456"/>')}
    with pytest.raises(ValidationError, match="speaks only the design's vocabulary"):
        checked_spec("drawing", hexed)


def test_the_roles_are_the_ones_the_lane_names_and_never_indigo() -> None:
    for role in (
        "ink-1",
        "ink-3",
        "rule-strong",
        "sunk",
        "chart-emph",
        "series-count",
        "elevation-7",
        "ph-5",
        "map-salt-hatch",
        "dip-4",
        "dye-cobalt",
        "terracotta",
        "madder",
    ):
        assert role in DRAWING_ROLES and role_problem(role) is None, role
    for role in (
        "indigo",
        "indigo-hover",
        "indigo-wash",
        "turmeric",
        "plate-metal",
        "fam-textiles",
        "ink-4",
        "rain-7",
        "error",
    ):
        assert role not in DRAWING_ROLES and role_problem(role) is not None, role
    assert role_problem("mol-bond") is not None and role_problem("mol-bond", molecules=True) is None


def test_a_paint_reads_tokens_mixes_references_and_the_plain_words() -> None:
    for fine in (
        "none",
        "transparent",
        "currentColor",
        "url(#weave)",
        "var(--ink-2)",
        "color-mix(in srgb, var(--ink-1) 30%, var(--sunk))",
    ):
        assert paint_problem(fine) is None, fine
    assert paint_problem("color-mix(in srgb, var(--ink-1) 30%, var(--indigo))") is not None


def test_inline_science_drawings_and_swatches_are_held_to_the_roles() -> None:
    spec = {
        "drawing": {
            "tag": "svg",
            "attrs": {"viewBox": "0 0 320 200"},
            "children": [
                {"tag": "rect", "attrs": {"fill": "var(--indigo)"}},
                {"tag": "mask", "children": [{"tag": "rect", "attrs": {"fill": "#fff"}}]},
                {"tag": "text", "attrs": {"font-size": "12", "font-family": "Arial"}, "children": ["CO"]},
            ],
        },
        "swatch": "--ink-1",
        "dips": ["--dye-indigo", "--chart-series"],
        "colour": "--map-land",
    }
    found = spec_design_problems(spec)
    assert any("a <rect>'s fill --indigo is indigo" in problem for problem in found)
    assert any("a <text> names a font" in problem for problem in found)
    assert "swatch names --ink-1; a swatch or dip shows a depicted --dye-* or --dip-* material" in found
    assert any(problem.startswith("dips[1] names --chart-series") for problem in found)
    assert len(found) == 4
