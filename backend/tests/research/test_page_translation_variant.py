from typing import Any

from app.research.monograph_page import MonographContent, render_page
from app.research.page_translation_variant import (
    NO_TRANSLATIONS,
    ServedTranslations,
    translations_digest,
    variant_content,
)
from app.research.translation_passages import unit_hash

SOURCE = {
    "number": 1,
    "title": "A dyer's handbook",
    "fullTitle": None,
    "publisher": None,
    "year": 2020,
    "grade": "A",
    "url": None,
    "extra": None,
    "dossierSourceId": None,
}
LEDE = [
    {
        "m": "s",
        "c": [
            "The cloth is dyed 3 times in an indigo ",
            {"m": "cite", "key": "c1", "g": ["g1"], "c": ["vat."]},
        ],
    }
]
PLANT = [{"m": "s", "c": ["The dye comes from a ", {"m": "cite", "key": "c2", "g": ["g1"], "c": ["shrub."]}]}]
HINDI_LEDE = ("कपड़े को नील के घोल में 3 बार ", "रंगा जाता है।")


def content(lede: list[Any] = LEDE, source_key: str = "g1") -> MonographContent:
    renumbered = [{**lede[0], "c": [lede[0]["c"][0], {**lede[0]["c"][1], "g": [source_key]}]}]
    return MonographContent.model_validate(
        {
            "craftSlug": "Kutch-Ajrakh",
            "sources": {source_key: SOURCE},
            "citations": {},
            "citationClaims": {},
            "data": {},
            "units": {
                "masthead-title": {
                    "chapter": "o",
                    "tag": "h1",
                    "field": None,
                    "nodes": ["Kutch Ajrakh"],
                    "claimIds": [],
                },
                "u1": {"chapter": "o", "tag": "p", "field": None, "nodes": renumbered, "claimIds": ["c-1"]},
                "u2": {"chapter": "o", "tag": "p", "field": None, "nodes": PLANT, "claimIds": ["c-2"]},
                "u3": {"chapter": "o", "tag": "dd", "field": None, "nodes": ["1998"], "claimIds": []},
            },
            "components": [],
            "layout": [],
        }
    )


def served(*, earlier: frozenset[str] = frozenset()) -> ServedTranslations:
    return ServedTranslations(by_hash={unit_hash(LEDE, ["c-1"]): HINDI_LEDE}, earlier=earlier, digest="d")


def test_a_translated_passage_is_drawn_in_its_language_and_every_other_passage_falls_back_marked_english() -> (
    None
):
    variant = variant_content(content(), served(), language="hi", source_version=4)
    units = variant.content.units
    assert units["u1"].lang == "hi" and units["u2"].lang == "en"
    assert units["u2"].nodes == PLANT
    assert units["masthead-title"].lang is None and units["u3"].lang is None
    assert units["u1"].nodes[0]["c"][0] == "कपड़े को नील के घोल में 3 बार "
    shown = variant.translation.model_dump(by_alias=True)
    assert shown == {
        "sourceLanguage": "en",
        "sourceVersion": 4,
        "script": "Deva",
        "direction": "ltr",
        "passages": 2,
        "translated": 1,
        "held": 0,
    }


def test_citations_are_the_english_passage_s_even_when_its_sources_were_numbered_again() -> None:
    variant = variant_content(content(source_key="g7"), served(), language="hi", source_version=1)
    cite = variant.content.units["u1"].nodes[0]["c"][1]
    assert cite == {"m": "cite", "key": "c1", "g": ["g7"], "c": ["रंगा जाता है।"]}


def test_a_passage_whose_english_changed_falls_back_and_is_counted_held() -> None:
    changed = [{**LEDE[0], "c": ["The cloth is dyed 4 times in an indigo ", LEDE[0]["c"][1]]}]
    variant = variant_content(
        content(changed), served(earlier=frozenset({"u1"})), language="hi", source_version=2
    )
    assert variant.content.units["u1"].lang == "en"
    assert (variant.translation.translated, variant.translation.held) == (0, 1)


def test_nothing_served_leaves_every_passage_marked_english() -> None:
    variant = variant_content(content(), NO_TRANSLATIONS, language="ur", source_version=1)
    assert variant.translation.direction == "rtl" and variant.translation.script == "Arab"
    assert {key: unit.lang for key, unit in variant.content.units.items()} == {
        "masthead-title": None,
        "u1": "en",
        "u2": "en",
        "u3": None,
    }


def test_a_drawn_passage_carries_its_language_and_a_fallback_says_it_is_english() -> None:
    variant = variant_content(content(), served(), language="hi", source_version=1)
    template = (
        '<main id="kv-main"><p><kv-slot unit="u1"></kv-slot></p><p><kv-slot unit="u2"></kv-slot></p></main>'
    )
    page = render_page(template, variant.content)
    assert '<p><span lang="hi" dir="ltr" data-script="Deva"><span class="s">कपड़े को नील के घोल में 3 बार ' in page
    assert '<p><span lang="en" dir="ltr" data-fallback="en"><span class="s">The dye comes from a ' in page
    english = render_page(template, content())
    assert "lang=" not in english and english.startswith('<main id="kv-main"><p><span class="s">The cloth')


def test_the_digest_follows_the_served_rows_whatever_their_order() -> None:
    assert translations_digest(["b", "a"]) == translations_digest(["a", "b"]) != translations_digest(["a"])
