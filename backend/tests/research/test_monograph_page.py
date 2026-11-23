import re
from typing import Any

import pytest

from app.core.errors import InvalidInput
from app.research.monograph_page import (
    UNIT_SLOT,
    CitedSource,
    MonographContent,
    TextUnit,
    assemble_template,
    render_nodes,
    render_page,
    slot,
    slot_keys,
)
from app.scripts.build_monograph import SERVED_FOLDERS, built_page, served_page_path
from app.services.monograph_document import monograph_content, monograph_shell, page_parts

GI_JOURNAL = CitedSource(
    number=1,
    title="GI Journal No. 188: Kutch Ajrakh",
    full_title=None,
    publisher=None,
    year=2023,
    grade="A",
    url=None,
    extra=None,
    dossier_source_id="S01",
)
RHYTHM = GI_JOURNAL.model_copy(
    update={"number": 2, "title": "Ajrakh: Rhythm of Blues", "dossier_source_id": None}
)
CASTE = GI_JOURNAL.model_copy(update={"number": 11, "title": "Ajrakh: From Caste Dress to Catwalk"})
SOURCES = {"g1": GI_JOURNAL, "g2": RHYTHM, "g11": CASTE}


def _content(units: dict[str, TextUnit], data: dict[str, Any] | None = None) -> MonographContent:
    return MonographContent(
        craft_slug="Kutch-Ajrakh",
        sources=SOURCES,
        citations={},
        citation_claims={},
        data=data or {},
        units=units,
        components=[],
        layout=[],
    )


def test_a_cited_sentence_renders_its_last_word_and_button_unbroken() -> None:
    nodes = [
        {
            "m": "s",
            "c": [
                "A resist printing and ",
                {"m": "cite", "key": "chem:q0", "g": ["g1", "g2"], "c": ["dyeing."]},
            ],
        }
    ]
    assert render_nodes(nodes, SOURCES) == (
        '<span class="s">A resist printing and <span class="nw">dyeing.<button class="kcite" type="button" '
        'data-c="chem:q0" data-g="g1 g2" aria-haspopup="dialog" aria-expanded="false" '
        'aria-label="Sources 1, 2" aria-description="GI Journal No. 188: Kutch Ajrakh; Ajrakh: Rhythm of Blues">'
        "1,2</button></span></span>"
    )


def test_a_unit_writes_an_apostrophe_and_a_straight_quote_as_entities_as_the_approved_page_does() -> None:
    nodes = [{"m": "s", "c": ['Finer than Barmer\'s "block" prints & <dyes>']}]
    assert render_nodes(nodes, SOURCES) == (
        '<span class="s">Finer than Barmer&#x27;s &quot;block&quot; prints &amp; &lt;dyes&gt;</span>'
    )


def test_a_citation_numbers_its_sources_in_order_but_keeps_their_given_order_in_data() -> None:
    nodes = [{"m": "cite", "key": "mb:aj:C001", "g": ["g2", "g1", "g11"], "c": ["catwalk."]}]
    rendered = render_nodes(nodes, SOURCES)
    assert 'data-g="g2 g1 g11"' in rendered
    assert 'aria-label="Sources 1, 2, 11"' in rendered
    assert (
        'aria-description="GI Journal No. 188: Kutch Ajrakh; Ajrakh: Rhythm of Blues; '
        'Ajrakh: From Caste Dress to Catwalk">1,2,11</button>'
    ) in rendered
    assert 'aria-label="Source 1"' in render_nodes(
        [{"m": "cite", "key": "k", "g": ["g1"], "c": ["x."]}], SOURCES
    )


def test_the_fixed_marks_render_as_the_page_wrote_them() -> None:
    nodes = [
        {"m": "i", "role": "bot", "c": ["Rubia cordifolia"]},
        " and ",
        {"m": "i", "c": ["kut"]},
        ", H",
        {"m": "sub", "c": ["2"]},
        "O, ",
        {
            "m": "link",
            "cls": "inline",
            "href": "#fig1",
            "c": [{"m": "figref", "ref": "chem:1", "c": ["Fig. 1"]}],
        },
        ", ",
        {
            "m": "link",
            "href": "https://example.org/a?b=1&c=2",
            "rel": "noopener",
            "target": "_blank",
            "c": ["a page"],
        },
        " & ",
        {"m": "span", "cls": "lk", "c": ["Cloth after"]},
    ]
    assert render_nodes(nodes, SOURCES) == (
        '<i class="bot">Rubia cordifolia</i> and <i>kut</i>, H<sub>2</sub>O, '
        '<a class="inline" href="#fig1"><span class="kv-figref" data-figref="chem:1">Fig. 1</span></a>, '
        '<a href="https://example.org/a?b=1&amp;c=2" rel="noopener" target="_blank">a page</a> &amp; '
        '<span class="lk">Cloth after</span>'
    )


def test_an_unknown_mark_or_source_is_refused() -> None:
    with pytest.raises(InvalidInput):
        render_nodes([{"m": "script", "c": []}], SOURCES)
    with pytest.raises(InvalidInput):
        render_nodes([{"m": "cite", "key": "k", "g": ["g9"], "c": []}], SOURCES)


def test_a_page_fills_its_unit_and_data_slots_and_escapes_closing_tags_in_data() -> None:
    unit = TextUnit(chapter="answer", tag="p", field="OVERVIEW", nodes=["Ajrakh"], claim_ids=[])
    template = f"<p>{slot('unit', 'u0001')}</p><script>{slot('data', 'film')}</script>"
    page = render_page(template, _content({"u0001": unit}, {"film": {"subs": ["<b>x</b>"]}}))
    assert page == '<p>Ajrakh</p><script>{"subs": ["<b>x<\\/b>"]}</script>'
    with pytest.raises(InvalidInput):
        render_page(slot("unit", "u0002"), _content({"u0001": unit}))


@pytest.mark.parametrize("slug", sorted(SERVED_FOLDERS))
def test_the_served_monograph_is_exactly_its_build(slug: str) -> None:
    assert built_page(slug) == served_page_path(slug).read_bytes().decode("utf-8")


@pytest.mark.parametrize("slug", sorted(SERVED_FOLDERS))
def test_the_content_holds_no_markup_and_every_unit_has_one_slot(slug: str) -> None:
    content = monograph_content(slug)
    template = assemble_template(monograph_shell(slug), page_parts(content))
    slots = slot_keys(template, UNIT_SLOT)
    assert sorted(slots) == sorted(content.units) and len(slots) == len(set(slots))

    def texts(nodes: list[Any]) -> list[str]:
        return [n for n in nodes if isinstance(n, str)] + [
            t for n in nodes if isinstance(n, dict) for t in texts(n.get("c", []))
        ]

    markup = [t for unit in content.units.values() for t in texts(unit.nodes) if re.search(r"<[a-zA-Z/!]", t)]
    assert markup == []


def test_chapter_names_name_each_chapter_of_the_layout_once_in_its_order() -> None:
    unit = TextUnit(chapter="cloth", tag="p", field="OVERVIEW", nodes=["Ajrakh"], claim_ids=[])
    content = _content({"u0001": unit, "u0002": unit.model_copy(update={"chapter": "made"})})
    layout = [
        {"chapter": "cloth", "kind": "unit", "ref": "u0001"},
        {"chapter": "made", "kind": "unit", "ref": "u0002"},
    ]
    body = content.model_dump(mode="json", by_alias=True) | {"layout": layout}
    named = [
        {"key": "cloth", "title": "The cloth", "rail": "The cloth"},
        {"key": "made", "title": "How it is made", "rail": "Making"},
    ]
    shown = MonographContent.model_validate(body | {"chapters": named})
    assert [(c.title, c.rail) for c in shown.chapters] == [
        ("The cloth", "The cloth"),
        ("How it is made", "Making"),
    ]
    assert "chapters" not in MonographContent.model_validate(body).model_dump(by_alias=True)
    with pytest.raises(ValueError, match="once, in its order"):
        MonographContent.model_validate(body | {"chapters": named[::-1]})


def test_kutch_ajrakhs_chapter_names_are_its_approved_rail_and_chapter_menu() -> None:
    template = monograph_shell("Kutch-Ajrakh")
    item = re.compile(r'<a href="#([a-z-]+)"[^>]*>(?:<b>[^<]*</b>)?<span>([^<]*)</span></a>')
    rail = item.findall(re.search(r'<ol id="kv-rail-list">(.*?)</ol>', template, re.S).group(1))
    menu = item.findall(re.search(r'id="kv-menu".*?<ol>(.*?)</ol>', template, re.S).group(1))
    labels = re.findall(r'<section class="kv-ch" id="([a-z-]+)" data-ch="\d+" data-label="([^"]+)"', template)
    named = monograph_content("Kutch-Ajrakh").chapters
    assert [(c.key, c.rail) for c in named] == rail
    assert [(c.key, c.title) for c in named] == menu == labels
    assert ("made", "Making") in rail and ("made", "How it is made") in menu
