import json
import re
from typing import Any

import pytest

from app.core.errors import InvalidInput
from app.research.component_specs_plates import SPEC_MODELS_PLATES
from app.research.monograph_page import CitedSource, MonographContent
from app.scripts.build_monograph import monograph_content
from app.scripts.extract_specs_files import extracted_specs, spec_path, stale_specs
from app.scripts.extract_specs_markup import find_anchor, parse_markup
from app.scripts.extract_specs_plates import PLATES

SLUG = "Kutch-Ajrakh"
UNIT_ID = re.compile(r"^u\d{4}$")
SOURCE = CitedSource(
    number=3,
    title="Ajrakh",
    full_title=None,
    publisher=None,
    year=None,
    grade="B",
    url=None,
    extra=None,
    dossier_source_id=None,
)
PLATE_MARKUP = (
    '<main><div class="kv-banni wrap"><figure class="plate "><div class="ph r32">'
    '<img src="/monographs/kutch-ajrakh/img/banni.jpg" width="1280" height="853" alt="Dry ground." loading="eager"></div>'
    '<figcaption><p class="cap"><kv-slot unit="u0720"></kv-slot></p><p class="credit"><kv-slot unit="u0721"></kv-slot></p>'
    '</figcaption></figure><div class="kv-banni-q"><blockquote class="kv-pull"><p><kv-slot unit="u0722"></kv-slot></p>'
    '<footer><span class="s">Khamir, <i>Khatris</i>, <span class="nw">Dhamadka<button class="kcite" type="button" '
    'data-c="pt:C035" data-g="g3" aria-label="Source 3">3</button></span></span></footer></blockquote></div></div></main>'
)


ATTRIBUTION = [
    {
        "m": "s",
        "c": [
            "Khamir, ",
            {"m": "i", "c": ["Khatris"]},
            ", ",
            {
                "m": "cite",
                "key": "pt:C035",
                "g": ["g3"],
                "shown": [{"number": 3, "title": "Ajrakh"}],
                "c": ["Dhamadka"],
            },
        ],
    }
]


def _content(kind: str, anchor: str) -> MonographContent:
    return MonographContent.model_validate(
        {
            "craftSlug": SLUG,
            "sources": {"g3": SOURCE.model_dump(by_alias=True)},
            "citations": {},
            "citationClaims": {},
            "data": {},
            "units": {},
            "components": [
                {
                    "label": "shared/geography/banni-photo",
                    "chapter": "why",
                    "anchor": anchor,
                    "kind": kind,
                    "title": "Banni",
                    "description": "The Banni.",
                    "field": "GEOGRAPHY",
                    "fields": [],
                    "subjects": [],
                }
            ],
            "layout": [],
        }
    )


def _units(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value} if UNIT_ID.match(value) else set()
    if isinstance(value, dict):
        return set().union(*(_units(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_units(item) for item in value), set())
    return set()


def test_markup_keeps_the_case_of_drawing_names_and_finds_an_anchor_once() -> None:
    tree = parse_markup(
        '<div id="a"><svg viewBox="0 0 2 2"><linearGradient id="g"/></svg><p alt="Fill me">x</p></div>'
    )
    svg = find_anchor(tree, "#a").elements()[0]
    assert svg.attrs == {"viewBox": "0 0 2 2"}
    assert svg.elements()[0].tag == "linearGradient"
    assert find_anchor(tree, '[alt="Fill me"]').text() == "x"
    with pytest.raises(InvalidInput, match="matches 0 elements"):
        find_anchor(tree, "#b")


def test_a_plate_with_a_pull_quote_becomes_its_picture_units_and_held_attribution() -> None:
    specs = extracted_specs(PLATES, _content("picture_plate", '[class="kv-banni wrap"]'), PLATE_MARKUP)
    spec = specs["shared/geography/banni-photo"].model_dump(mode="json", by_alias=True)
    assert spec["setting"] == "pull"
    assert spec["picture"] == {
        "src": "/monographs/kutch-ajrakh/img/banni.jpg",
        "width": 1280,
        "height": 853,
        "alt": "Dry ground.",
        "loading": "eager",
        "fetchPriority": None,
        "decoding": None,
    }
    assert spec["figure"] == {
        "classes": [],
        "crop": "r32",
        "captions": [{"unit": "u0720", "look": False}],
        "credit": "u0721",
    }
    assert spec["pull"] == {
        "classes": ["kv-banni", "wrap"],
        "box": "kv-banni-q",
        "quote": "u0722",
        "attribution": ATTRIBUTION,
    }


def test_an_attribution_that_is_a_text_unit_is_named_by_its_unit() -> None:
    footer = re.search(r"<footer>.*</footer>", PLATE_MARKUP)
    assert footer is not None
    markup = PLATE_MARKUP.replace(footer.group(0), '<footer> <kv-slot unit="u0723"></kv-slot> </footer>')
    specs = extracted_specs(PLATES, _content("picture_plate", '[class="kv-banni wrap"]'), markup)
    spec = specs["shared/geography/banni-photo"].model_dump(mode="json", by_alias=True)
    assert spec["pull"]["attribution"] == "u0723"
    assert _units(spec) == {"u0720", "u0721", "u0722", "u0723"}


def test_a_held_citation_showing_other_numbers_than_its_sources_is_refused() -> None:
    wrong = PLATE_MARKUP.replace('aria-label="Source 3">3<', 'aria-label="Source 4">4<')
    with pytest.raises(InvalidInput, match="other numbers"):
        extracted_specs(PLATES, _content("picture_plate", '[class="kv-banni wrap"]'), wrong)


@pytest.fixture(scope="module")
def ajrakh() -> MonographContent:
    return monograph_content(SLUG)


def test_every_ajrakh_plate_component_has_a_spec_file_that_validates(ajrakh: MonographContent) -> None:
    plates = [component for component in ajrakh.components if component.kind in SPEC_MODELS_PLATES]
    assert len(plates) == 27
    for component in plates:
        raw = spec_path(SLUG, component.label).read_bytes().decode("utf-8")
        SPEC_MODELS_PLATES[component.kind].model_validate_json(raw)


def test_each_ajrakh_plate_spec_shows_exactly_the_units_its_component_holds(ajrakh: MonographContent) -> None:
    for component in ajrakh.components:
        if component.kind not in SPEC_MODELS_PLATES:
            continue
        spec = json.loads(spec_path(SLUG, component.label).read_bytes().decode("utf-8"))
        within = {
            entry.ref for entry in ajrakh.layout if entry.kind == "unit" and entry.within == component.label
        }
        assert _units(spec) == within, component.label


def test_the_committed_plate_specs_are_what_extraction_writes() -> None:
    assert stale_specs(PLATES, SLUG) == []
