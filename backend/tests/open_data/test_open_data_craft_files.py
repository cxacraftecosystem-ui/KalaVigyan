import json

import pytest

from app.services.open_data_changes import release_changes
from app.services.open_data_deposit import release_folder
from app.services.open_data_files import release_files

from .release_fixtures import AJRAKH, AJRAKH_STAMP, SITE, STAMP, empty_tables

NO_CHANGES = release_changes({}, None, None)
CREATOR = "KalaVigyan, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform, IIT Kharagpur"
PAGE = "https://kalavigyan.example/crafts/Kutch-Ajrakh"


def _craft_files() -> dict[str, str]:
    built = release_files(empty_tables(), AJRAKH_STAMP, NO_CHANGES, site=SITE, scope=AJRAKH)
    return {name: body.decode("utf-8") for name, body in built.files.items()}


def test_a_craft_release_keeps_every_table_and_file_of_the_whole_release() -> None:
    whole = release_files(empty_tables(), STAMP, NO_CHANGES, site=SITE).files
    assert set(_craft_files()) == set(whole)
    assert _craft_files()["claims.jsonl"] == "" and len(whole) == 2 * 14 + 5


def test_its_descriptor_names_the_craft_and_reads_back_as_the_craft_s_release() -> None:
    files = _craft_files()
    package = json.loads(files["datapackage.json"])
    assert (package["name"], package["title"]) == (
        "kalavigyan-open-knowledge-kutch-ajrakh",
        "Kutch Ajrakh: KalaVigyan open knowledge",
    )
    assert package["craft"] == {"slug": "Kutch-Ajrakh", "name": "Kutch Ajrakh", "path": PAGE}
    assert package["keywords"][-1] == "Kutch Ajrakh"
    assert package["description"].startswith("The slice of KalaVigyan's knowledge about Kutch Ajrakh")
    assert package["licenses"][0]["name"] == "CC-BY-4.0"
    whole = json.loads(release_files(empty_tables(), STAMP, NO_CHANGES, site=SITE).files["datapackage.json"])
    assert "craft" not in whole and whole["name"] == "kalavigyan-open-knowledge"
    built = release_files(empty_tables(), AJRAKH_STAMP, NO_CHANGES, site=SITE, scope=AJRAKH)
    assert release_folder(built.files).scope == AJRAKH


def test_its_readme_says_it_is_the_craft_s_slice_with_its_counts_what_stays_out_and_the_monograph() -> None:
    readme = _craft_files()["README.md"]
    assert readme.startswith("# Kutch Ajrakh: KalaVigyan open knowledge\n")
    assert "The slice of KalaVigyan's knowledge about Kutch Ajrakh" in readme
    assert (
        f"{CREATOR}. (2026). Kutch Ajrakh: KalaVigyan open knowledge (Version 2026.11.21) [Data set]. "
        "Zenodo. https://doi.org/10.5072/zenodo.200"
    ) in readme
    assert "@misc{kalavigyan_kutch_ajrakh_2026_11_21," in readme
    assert "| Facts | `claims.jsonl`, `claims.csv` | 0 |" in readme
    assert "- The names of contributors and reviewers.\n" in readme
    assert f"The monograph of Kutch Ajrakh: {PAGE}." in readme
    assert "released as KalaVigyan open knowledge: https://kalavigyan.example/data." in readme


def test_its_citation_file_carries_the_craft_s_title_keyword_and_page() -> None:
    cff = _craft_files()["CITATION.cff"]
    assert 'title: "Kutch Ajrakh: KalaVigyan open knowledge"' in cff
    assert f'  - type: url\n    value: "{PAGE}"\n    description: "The monograph of Kutch Ajrakh"\n' in cff
    assert '  - "Kutch Ajrakh"\nabstract: "The slice of' in cff
    assert "license: CC-BY-4.0" in cff
    whole = release_files(empty_tables(), STAMP, NO_CHANGES, site=SITE).files["CITATION.cff"].decode("utf-8")
    assert "type: url" not in whole and 'title: "KalaVigyan open knowledge"' in whole


def test_a_release_whose_words_and_stamp_name_different_scopes_is_refused() -> None:
    with pytest.raises(ValueError, match="stamp names"):
        release_files(empty_tables(), STAMP, NO_CHANGES, site=SITE, scope=AJRAKH)
    with pytest.raises(ValueError, match="stamp names"):
        release_files(empty_tables(), AJRAKH_STAMP, NO_CHANGES, site=SITE)
