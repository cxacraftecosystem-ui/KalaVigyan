from typing import Any

import pytest

from app.core.errors import InvalidInput
from app.research.monograph_document import fragment_file_name
from app.research.monograph_page import (
    COMPONENT_SLOT,
    UNIT_SLOT,
    MonographContent,
    assemble_template,
    kit_parts,
    slot_keys,
)
from app.scripts.build_monograph import PUBLIC_KIT_DIR, SERVED_KIT_PREAMBLES, served_page_path
from app.scripts.split_monograph import Span, anchor_span, split_template, tags
from app.services.monograph_document import (
    FRAGMENTS_FOLDER,
    MONOGRAPHS_DIR,
    kit_sources,
    monograph_content,
    monograph_shell,
    page_parts,
)

SLUG = "Kutch-Ajrakh"
OUTER = "t/x/outer"
INNER = "t/x/inner"
MODEL = "t/x/model"
TEMPLATE = (
    '<!doctype html><html><head><script>theme()</script><style>p{}</style><style id="kv-release-fixes">q{}</style>'
    '</head><body><figure id="fig1"><kv-slot unit="u1"></kv-slot><div class="plate a"><img src="x.png">'
    '<kv-slot unit="u2"></kv-slot></div></figure><p><kv-slot unit="u3"></kv-slot></p>'
    '<div class="model"><style>.m{}</style><kv-slot unit="u4"></kv-slot></div>'
    '<script type="application/json" id="d"><kv-slot data="film"></kv-slot></script>'
    "<script>page('</div>')</script><script>KV.boot()</script></body></html>"
)
COMPONENTS = {OUTER: "#fig1", INNER: '[class="plate a"]', MODEL: '[class="model"]'}
PLACED = {"u1": OUTER, "u2": INNER, "u3": None, "u4": MODEL, OUTER: None, INNER: OUTER, MODEL: None}


def _content(anchors: dict[str, str] = COMPONENTS, placed: dict[str, Any] = PLACED) -> MonographContent:
    component = {
        "chapter": "c",
        "kind": "picture_plate",
        "title": "T",
        "description": "D.",
        "field": "CHEMISTRY",
    }
    return MonographContent.model_validate(
        {
            "craftSlug": "Split-Test",
            "sources": {},
            "citations": {},
            "citationClaims": {},
            "data": {},
            "units": {},
            "components": [
                component | {"label": label, "anchor": anchor, "fields": [], "subjects": []}
                for label, anchor in anchors.items()
            ],
            "layout": [
                {"chapter": "c", "kind": "component" if "/" in ref else "unit", "ref": ref, "within": within}
                for ref, within in placed.items()
            ],
        }
    )


def test_each_component_leaves_a_slot_and_the_page_wide_styles_and_body_scripts_go_to_the_kit() -> None:
    split = split_template(TEMPLATE, _content())
    assert split.shell == (
        '<!doctype html><html><head><script>theme()</script><style><kv-slot kit="monograph.css#page"></kv-slot>'
        '</style><style id="kv-release-fixes"><kv-slot kit="monograph.css#release-fixes"></kv-slot></style>'
        '</head><body><kv-slot component="t/x/outer"></kv-slot><p><kv-slot unit="u3"></kv-slot></p>'
        '<kv-slot component="t/x/model"></kv-slot>'
        '<script type="application/json" id="d"><kv-slot data="film"></kv-slot></script>'
        '<script><kv-slot kit="monograph.js#page"></kv-slot></script>'
        '<script><kv-slot kit="monograph.js#boxes"></kv-slot></script></body></html>'
    )
    assert split.fragments == {
        OUTER: '<figure id="fig1"><kv-slot unit="u1"></kv-slot><kv-slot component="t/x/inner"></kv-slot></figure>',
        INNER: '<div class="plate a"><img src="x.png"><kv-slot unit="u2"></kv-slot></div>',
        MODEL: '<div class="model"><style>.m{}</style><kv-slot unit="u4"></kv-slot></div>',
    }
    assert split.kit == {
        "monograph.css": "@kv-part page;\np{}\n@kv-part release-fixes;\nq{}\n",
        "monograph.js": '"kv-part page";\npage(\'</div>\')\n"kv-part boxes";\nKV.boot()\n',
    }
    assert assemble_template(split.shell, split.parts()) == TEMPLATE


@pytest.mark.parametrize(
    ("template", "anchors", "placed", "message"),
    [
        (TEMPLATE, COMPONENTS | {OUTER: "#nowhere"}, PLACED, "selects 0 elements"),
        (TEMPLATE.replace("<p>", '<p class="plate a">'), COMPONENTS, PLACED, "selects 2 elements"),
        (TEMPLATE, COMPONENTS | {OUTER: ".plate"}, PLACED, "neither #id"),
        (TEMPLATE, COMPONENTS, PLACED | {"u3": OUTER}, "inside other components"),
        (TEMPLATE, COMPONENTS, PLACED | {INNER: None}, "inside other components"),
        (
            TEMPLATE.replace("</body>", "<script>more()</script></body>"),
            COMPONENTS,
            PLACED,
            "page-wide script",
        ),
    ],
    ids=[
        "no element",
        "two elements",
        "not a known anchor form",
        "a unit misplaced",
        "a nesting unrecorded",
        "an extra script",
    ],
)
def test_a_page_the_content_does_not_describe_is_refused(
    template: str, anchors: dict[str, str], placed: dict[str, Any], message: str
) -> None:
    with pytest.raises(InvalidInput, match=message):
        split_template(template, _content(anchors, placed))


@pytest.fixture(scope="module")
def ajrakh() -> tuple[MonographContent, str, dict[str, str]]:
    content = monograph_content(SLUG)
    folder = MONOGRAPHS_DIR / SLUG / FRAGMENTS_FOLDER
    fragments = {path.name: path.read_bytes().decode("utf-8") for path in sorted(folder.iterdir())}
    return content, monograph_shell(SLUG), fragments


def test_splitting_the_assembled_page_again_gives_back_the_stored_shell_fragments_and_kit(
    ajrakh: tuple[MonographContent, str, dict[str, str]],
) -> None:
    content, shell, stored = ajrakh
    split = split_template(assemble_template(shell, page_parts(content)), content)
    assert split.shell == shell
    assert {fragment_file_name(label): text for label, text in split.fragments.items()} == stored
    assert split.kit == kit_sources()


def test_every_component_has_one_fragment_and_one_slot_and_its_fragment_is_the_element_its_anchor_selects(
    ajrakh: tuple[MonographContent, str, dict[str, str]],
) -> None:
    content, shell, stored = ajrakh
    assert len(content.components) == 80
    assert sorted(stored) == sorted(fragment_file_name(c.label) for c in content.components)
    slots = slot_keys(shell + "".join(stored.values()), COMPONENT_SLOT)
    assert sorted(slots) == sorted(c.label for c in content.components)
    for component in content.components:
        fragment = stored[fragment_file_name(component.label)]
        assert anchor_span(tags(fragment), component.anchor, component.label) == Span(0, len(fragment))


def test_every_unit_and_component_slot_sits_in_the_fragment_its_layout_entry_names(
    ajrakh: tuple[MonographContent, str, dict[str, str]],
) -> None:
    content, shell, stored = ajrakh
    holders = {None: shell} | {c.label: stored[fragment_file_name(c.label)] for c in content.components}
    for entry in content.layout:
        kind = UNIT_SLOT if entry.kind == "unit" else COMPONENT_SLOT
        assert entry.ref in slot_keys(holders[entry.within], kind), entry


def test_the_kit_the_web_app_loads_is_what_the_static_page_inlines() -> None:
    page = served_page_path(SLUG).read_bytes().decode("utf-8")
    elements = {
        "monograph.css": ("<style>", '<style id="kv-release-fixes">'),
        "monograph.js": ("<script>", "<script>"),
    }
    for name, source in kit_sources().items():
        parts = kit_parts(source, file_name=name)
        served = (PUBLIC_KIT_DIR / name).read_bytes().decode("utf-8")
        assert served == SERVED_KIT_PREAMBLES.get(name, "") + "".join(parts.values())
        closing = elements[name][0].replace("<", "</")
        inlined = "".join(
            f"{opening}{text}{closing}" for opening, text in zip(elements[name], parts.values(), strict=True)
        )
        assert inlined in page
