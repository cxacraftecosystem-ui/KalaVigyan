import copy
from typing import Any

import pytest

from app.data import river_names as river_names_module
from app.data.river_names import RiverNames, checkable, name_forms, parse_river_names
from app.geo.datasets import registry_row_ref
from app.services import stated_names

ENGLISH = frozenset({"river", "lime"})


def name_file(code: str, rivers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "dataset": {
            "code": code,
            "title": f"{code} title",
            "publisher": "Publisher",
            "edition": "2026-11-23",
            "period": "2026-11-23",
            "nativeResolution": "item coordinates",
            "licence": "CC0 1.0",
            "licenceUrl": "https://creativecommons.org/publicdomain/zero/1.0/",
            "attribution": "Attribution",
            "citation": None,
            "url": "https://query.wikidata.org/sparql",
            "retrievedAt": "2026-11-23T10:15:00+00:00",
            "sha256": "c" * 64,
        },
        "rivers": rivers,
    }


def river(name: str, refs: list[str], reaches: list[int], districts: list[int]) -> dict[str, Any]:
    return {
        "name": name,
        "refs": refs,
        "mainRiv": reaches[-1],
        "reachIds": reaches,
        "districtLgds": districts,
    }


WIKIDATA = name_file("WIKIDATA_RIVER_NAMES", [river("Narmada", ["Q234004"], [1, 2], [449])])
OSM = name_file(
    "OSM_RIVER_NAMES",
    [
        river("Suran River", ["way/1001"], [3], [449]),
        river("Son River", ["way/1002"], [4], [450]),
        river("Lime", ["way/1003"], [5], [451]),
        river("Devi", ["way/1004"], [6], [452]),
    ],
)


def names() -> RiverNames:
    return parse_river_names([WIKIDATA, OSM], ENGLISH)


def test_each_reach_carries_the_name_of_the_set_that_names_it() -> None:
    found = names()
    assert (found.of_reach(1).name, found.of_reach(1).dataset_code) == ("Narmada", "WIKIDATA_RIVER_NAMES")
    assert found.of_reach(3).refs == ("way/1001",) and found.of_reach(9) is None
    assert found.dataset("OSM_RIVER_NAMES")["sha256"] == "c" * 64


def test_a_reach_named_twice_or_a_file_of_another_schema_is_refused() -> None:
    twice = name_file("OSM_RIVER_NAMES", [river("Other", ["way/9"], [1], [449])])
    with pytest.raises(ValueError, match="reach 1 is named twice"):
        parse_river_names([WIKIDATA, twice], ENGLISH)
    older = copy.deepcopy(OSM) | {"schemaVersion": 0}
    with pytest.raises(ValueError, match="schema version 1"):
        parse_river_names([older], ENGLISH)


def test_a_name_s_forms_drop_its_brackets_and_its_word_for_river() -> None:
    assert name_forms("Dhamadka River (Suran)") == ("Dhamadka River", "Suran", "Dhamadka")
    assert name_forms("Narmada") == ("Narmada",)


def test_a_dossier_river_is_matched_by_a_form_of_its_name_in_its_district() -> None:
    found = names()
    assert found.place_river("Dhamadka River (Suran)", 449).name == "Suran River"
    assert found.place_river("Dhamadka River (Suran)", 450) is None
    assert found.place_river("Narmada River", None).dataset_code == "WIKIDATA_RIVER_NAMES"
    twins = name_file(
        "OSM_RIVER_NAMES", [river("Suran", ["way/7"], [7], [449]), river("Suran", ["way/8"], [8], [449])]
    )
    assert parse_river_names([twins], ENGLISH).place_river("Suran", 449) is None


def test_only_names_unlike_ordinary_words_are_checked_in_prose() -> None:
    assert checkable("Son River", ENGLISH) and checkable("Narmada", ENGLISH)
    assert (
        not checkable("Son", ENGLISH) and not checkable("Lime", ENGLISH) and not checkable("O'Neil", ENGLISH)
    )
    assert names().named_in("Devi saw the Indus.") == []
    assert names().named_in("The Son River meets the Narmada near Suran; Lime is ground.") == [
        "Son River",
        "Narmada",
    ]
    assert names().named_in("Dyers rinse in the Suran River.") == ["Suran River"]


def test_a_river_name_no_cited_claim_or_quote_states_is_unstated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stated_names, "load_river_names", names)
    assert stated_names.unstated_names("Dyers washed cloth in the Narmada.", ["dyers washed cloth"]) == [
        "Narmada"
    ]
    assert stated_names.unstated_names("Dyers washed cloth in the Narmada.", ["the narmada river"]) == []
    assert stated_names.unstated_names("The Son River flows on.", []) == ["Son River"]


def test_a_names_file_s_dataset_row_is_cited_with_its_reading_date() -> None:
    row = registry_row_ref(names().dataset("WIKIDATA_RIVER_NAMES"))
    assert (row.code, row.edition, str(row.read_on), row.sha256) == (
        "WIKIDATA_RIVER_NAMES",
        "2026-11-23",
        "2026-11-23",
        "c" * 64,
    )


def test_the_vendored_names_load_with_their_dataset_rows() -> None:
    river_names_module.load_river_names.cache_clear()
    loaded = river_names_module.load_river_names()
    assert [names_set.code for names_set in loaded.sets] == ["WIKIDATA_RIVER_NAMES", "OSM_RIVER_NAMES"]
    assert loaded.dataset("OSM_RIVER_NAMES")["attribution"] == "© OpenStreetMap contributors"
    assert loaded.dataset("OSM_RIVER_NAMES")["licence"] == "ODbL 1.0"
    assert loaded.dataset("WIKIDATA_RIVER_NAMES")["licence"] == "CC0 1.0"
    assert all(river.reach_ids and river.name for names_set in loaded.sets for river in names_set.rivers)
