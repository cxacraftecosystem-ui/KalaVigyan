import json

from app.scripts.write_component_homes import DEFS_FILE, defs_text
from app.services.document_kit_defs import (
    defined_ids,
    kit_defs,
    kit_defs_of,
    kit_style_references,
    kit_style_references_of,
    referenced_ids,
    spec_ids,
)
from app.services.monograph_document import MONOGRAPHS_DIR

AJRAKH = MONOGRAPHS_DIR / "Kutch-Ajrakh"
GRADIENT = '<radialGradient id="ag-C" cx=".3"><stop offset="0"/><stop offset="1"/></radialGradient>'
WEAVE = '<pattern id="chem-weave" width="3"><path d="M0 3 L3 0"/></pattern>'
OTHER_WEAVE = '<pattern id="chem-weave" width="9"><path d="M0 0"/></pattern>'


def shell(*definitions: str, scope: str = "chem") -> str:
    defs = "".join(definitions)
    return f'<main><div class="bx bx-{scope}"><svg class="kv-defs" width="0" height="0"><defs>{defs}</defs></svg></div></main>'


def test_each_definition_is_kept_once_in_the_order_the_shells_give_it() -> None:
    found = kit_defs_of([shell(GRADIENT, WEAVE), shell(OTHER_WEAVE, scope="pt")])
    assert list(found) == ["ag-C", "chem-weave"]
    assert found["ag-C"] == {"scope": "chem", "markup": GRADIENT}
    assert found["chem-weave"] == {"scope": "chem", "markup": WEAVE}


def test_a_shell_without_a_defs_block_gives_nothing() -> None:
    assert kit_defs_of(['<svg class="figure"><defs>' + GRADIENT + "</defs></svg>"]) == {}


def test_a_fragment_s_symbols_and_defs_serve_every_page_that_borrows_a_figure_using_them() -> None:
    symbol = '<symbol id="ai-vat" viewBox="0 0 1200 800"><rect width="1200" height="800"/></symbol>'
    fragment = f'<figure><svg><defs>{WEAVE}</defs>{symbol}<use href="#ai-vat"/></svg></figure>'
    found = kit_defs_of([shell(GRADIENT)], [("sa", fragment)])
    assert list(found) == ["ag-C", "chem-weave", "ai-vat"]
    assert found["ai-vat"] == {"scope": "sa", "markup": symbol}
    assert found["chem-weave"] == {"scope": "sa", "markup": WEAVE}


def test_references_and_definitions_are_read_from_markup() -> None:
    assert referenced_ids('fill="url(#ag-C)" <use href="#tile-1"/> <use x="1" href=\'#ag-H\'/>') == {
        "ag-C",
        "tile-1",
        "ag-H",
    }
    assert referenced_ids('<a href="#sources">Sources</a>') == set()
    assert defined_ids(GRADIENT + WEAVE) == {"ag-C", "chem-weave"}


def test_a_spec_s_use_elements_name_what_they_draw_and_its_ids_what_it_defines() -> None:
    spec = {
        "drawing": {
            "tag": "svg",
            "children": [
                {"tag": "use", "attrs": {"href": "#hd-plait"}},
                {"tag": "a", "attrs": {"href": "#fig1"}},
                {
                    "tag": "g",
                    "attrs": {"id": "cloth"},
                    "children": [{"tag": "use", "attrs": {"xlink:href": "#cloth"}}],
                },
            ],
        }
    }
    assert spec_ids(spec) == ({"hd-plait", "cloth"}, {"cloth"})


def test_every_reference_in_kutch_ajrakh_s_specs_and_fragments_resolves_on_any_page() -> None:
    kit = set(kit_defs())
    for path in sorted((AJRAKH / "specs").glob("*.json")):
        text = path.read_text(encoding="utf-8")
        used, defined = spec_ids(json.loads(text))
        missing = (used | referenced_ids(text)) - defined - kit
        assert not missing, f"{path.name} draws with {sorted(missing)}, which no page defines"
    for path in sorted((AJRAKH / "fragments").glob("*.html")):
        markup = path.read_text(encoding="utf-8")
        missing = referenced_ids(markup) - defined_ids(markup) - kit
        assert not missing, f"{path.name} draws with {sorted(missing)}, which no page defines"


def test_the_kit_style_names_the_patterns_it_fills_with_under_each_scope() -> None:
    css = (
        ".bx-pt .days-plot .dhatch{ fill: url(#hatch-madder) }\n"
        "@media (min-width: 40em) { .bx-sa .loc .dist.on{fill:url(#hatch-place)} .bx-sa .x{color:red} }\n"
        ".bx-pt .a, .bx-mb .a { fill: url(#pt-weave); stroke: url(#hatch-madder) }\n"
        ".plain { fill: url(#loose) }"
    )
    assert kit_style_references_of(css) == {
        "mb": ["hatch-madder", "pt-weave"],
        "pt": ["hatch-madder", "pt-weave"],
        "sa": ["hatch-place"],
    }


def test_the_kit_style_fills_the_madder_hatch_and_the_place_hatch() -> None:
    assert kit_style_references() == {"pt": ["hatch-madder"], "sa": ["hatch-place"]}


def test_the_committed_kit_defs_are_the_build() -> None:
    assert DEFS_FILE.read_bytes().decode("utf-8") == defs_text()
