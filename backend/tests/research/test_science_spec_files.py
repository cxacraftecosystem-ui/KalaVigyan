import re
from collections.abc import Iterator
from typing import Any

import pytest

from app.research.component_specs_science import SPEC_MODELS_SCIENCE
from app.research.monograph_document import spec_file_name
from app.research.monograph_page import MonographContent
from app.scripts.build_monograph import monograph_content
from app.scripts.extract_specs_science import extract_specs, specs_dir, stale_specs

SLUG = "Kutch-Ajrakh"
UNIT = re.compile(r"^u\d{4,}$")
SCIENCE_COMPONENTS_IN_AJRAKH = 21
NESTED = {
    "kutch-ajrakh/chemistry/what-if-lab": [
        "kutch-ajrakh/chemistry/what-if-indigo-vat",
        "kutch-ajrakh/chemistry/what-if-red-dye",
        "kutch-ajrakh/chemistry/what-if-wash-water",
    ],
    "kutch-ajrakh/chemistry/what-if-indigo-vat": ["kutch-ajrakh/process/vat-setting-days"],
    "kutch-ajrakh/chemistry/what-if-red-dye": ["kutch-ajrakh/process/red-bath-hours"],
    "kutch-ajrakh/materials/six-materials": ["kutch-ajrakh/materials/natural-dye-materials-photo"],
}
STRUCTURES = (
    "shared/chemistry/alizarin-aluminium-ring-structures",
    "shared/chemistry/alizarin-purpurin-structures-hindi",
)
RECORD_CITES = [
    (
        6293,
        {
            "m": "cite",
            "key": "rm:mol.1",
            "g": ["g35"],
            "shown": [{"number": 35, "title": "Alizarin, PubChem CID 6293"}],
            "c": [],
        },
    ),
    (
        6683,
        {
            "m": "cite",
            "key": "rm:mol.6683",
            "g": ["g36"],
            "shown": [{"number": 36, "title": "Purpurin, PubChem CID 6683"}],
            "c": [],
        },
    ),
]


@pytest.fixture(scope="module")
def content() -> MonographContent:
    return monograph_content(SLUG)


@pytest.fixture(scope="module")
def specs(content: MonographContent) -> dict[str, tuple[str, dict[str, Any]]]:
    found = {}
    for component in content.components:
        if component.kind in SPEC_MODELS_SCIENCE:
            text = (specs_dir(SLUG) / spec_file_name(component.label)).read_bytes().decode("utf-8")
            model = SPEC_MODELS_SCIENCE[component.kind].model_validate_json(text)
            found[component.label] = (component.kind, model.model_dump(mode="json", by_alias=True))
    return found


def strings(value: Any) -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for key, inner in value.items():
            if isinstance(inner, str):
                yield key, inner
            else:
                yield from strings(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from strings(inner)


def units_of(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value} if UNIT.match(value) else set()
    inner = value.values() if isinstance(value, dict) else value if isinstance(value, list) else []
    return set().union(*(units_of(item) for item in inner))


def test_every_ajrakh_component_of_a_science_kind_has_a_valid_spec_file(specs: dict[str, Any]) -> None:
    assert len(specs) == SCIENCE_COMPONENTS_IN_AJRAKH


def test_a_spec_shows_exactly_the_units_the_layout_places_in_its_component(
    content: MonographContent, specs: dict[str, tuple[str, dict[str, Any]]]
) -> None:
    within: dict[str, set[str]] = {}
    for entry in content.layout:
        if entry.within is not None and entry.kind == "unit":
            within.setdefault(entry.within, set()).add(entry.ref)
    for label, (_kind, spec) in specs.items():
        shown = units_of(spec)
        assert shown <= set(content.units), label
        assert shown == within.get(label, set()), label


def test_a_spec_places_its_nested_components_where_the_page_nests_them(
    specs: dict[str, tuple[str, dict[str, Any]]],
) -> None:
    nested = {
        label: [text for key, text in strings(spec) if key == "component"]
        for label, (_kind, spec) in specs.items()
    }
    assert {label: found for label, found in nested.items() if found} == NESTED


def test_no_cited_passage_of_a_science_component_sits_outside_a_text_unit() -> None:
    assert [(item.label, item.citation) for item in extract_specs(SLUG).held] == []


def test_each_structure_carries_the_citation_of_its_pubchem_record(
    specs: dict[str, tuple[str, dict[str, Any]]],
) -> None:
    for label in STRUCTURES:
        _kind, spec = specs[label]
        assert [(molecule["cid"], molecule["recordCite"]) for molecule in spec["molecules"]] == RECORD_CITES


def test_the_committed_spec_files_are_what_the_template_extracts_to() -> None:
    assert stale_specs(SLUG) == []
