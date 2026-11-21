import json

import pytest

from app.core.errors import InvalidInput
from app.services.open_data_changes import release_changes
from app.services.open_data_deposit import release_folder
from app.services.open_data_files import csv_bytes, jsonl_bytes, manifest_text, release_files, sha256_of
from app.services.open_data_structure_tables import MATERIALS
from app.services.open_data_tables import FAMILIES, TABLES

from .release_fixtures import SITE, STAMP, empty_tables, family_row, tables_with

EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
NO_CHANGES = release_changes({}, None, None)
FILES = {
    *(f"{table.name}.jsonl" for table in TABLES),
    *(f"{table.name}.csv" for table in TABLES),
    "datapackage.json",
    "README.md",
    "CITATION.cff",
    "CHANGES.md",
    "SHA256SUMS",
}
ALUM = {
    "craft": "Kutch-Ajrakh",
    "key": "M01",
    "name": "Alum",
    "tool": False,
    "kind": "MORDANT",
    "role": "MORDANT",
    "local_names": ["fatakdi", "phitkari"],
    "botanical_name": None,
    "pubchem_cid": 24856,
    "claim_ids": ["c1"],
}


def test_a_json_lines_file_holds_one_compact_record_per_line_in_column_order() -> None:
    rows = [family_row("Embroidery", "Embroidery", 2), family_row("Block-Printing", "Block printing", 1)]
    assert jsonl_bytes(FAMILIES, rows) == (
        b'{"slug":"Embroidery","name":"Embroidery","category":"Textiles-Based-Craft-Category","sort_order":2}\n'
        b'{"slug":"Block-Printing","name":"Block printing","category":"Textiles-Based-Craft-Category","sort_order":1}\n'
    )


def test_a_csv_view_writes_lists_as_json_an_empty_cell_for_no_value_and_words_for_booleans() -> None:
    assert csv_bytes(MATERIALS, [ALUM]).decode("utf-8") == (
        "craft,key,name,tool,kind,role,local_names,botanical_name,pubchem_cid,claim_ids\n"
        'Kutch-Ajrakh,M01,Alum,false,MORDANT,MORDANT,"[""fatakdi"",""phitkari""]",,24856,"[""c1""]"\n'
    )


def test_native_script_text_stays_utf8_and_unescaped() -> None:
    row = {"craft": "Kutch-Ajrakh", "text": "અજરખ", "language": "gu", "script": "Gujr", "claim_id": "c1"}
    native = next(table for table in TABLES if table.name == "native_names")
    assert "અજરખ".encode() in jsonl_bytes(native, [row])
    assert "અજરખ".encode() in csv_bytes(native, [row])


def test_the_manifest_lists_every_other_file_by_its_sha256_in_name_order() -> None:
    files = {"b.txt": b"abc", "a.txt": b"", "SHA256SUMS": b"anything"}
    assert manifest_text(files) == f"{EMPTY_SHA256}  a.txt\n{ABC_SHA256}  b.txt\n"
    assert sha256_of(b"abc") == ABC_SHA256


def test_a_release_holds_two_files_per_table_and_the_five_about_it() -> None:
    built = release_files(empty_tables(), STAMP, NO_CHANGES, site=SITE)
    assert set(built.files) == FILES
    assert len(built.files) == 2 * 14 + 5
    assert built.files["claims.jsonl"] == b""
    assert built.files["claims.csv"].decode("utf-8").startswith("id,text,language,field,fields,level,status")


def test_the_same_data_builds_the_same_bytes() -> None:
    tables = tables_with(families=[family_row("Embroidery", "Embroidery", 2)])
    first = release_files(tables, STAMP, NO_CHANGES, site=SITE)
    second = release_files(tables, STAMP, NO_CHANGES, site=SITE)
    assert first.files == second.files
    assert first.manifest_sha256() == second.manifest_sha256()


def test_the_descriptor_describes_every_field_and_hashes_every_data_file() -> None:
    built = release_files(empty_tables(), STAMP, NO_CHANGES, site=SITE)
    package = json.loads(built.files["datapackage.json"])
    assert (package["id"], package["version"], package["licenses"][0]["name"]) == (
        "https://doi.org/10.5072/zenodo.200",
        "2026.11.21",
        "CC-BY-4.0",
    )
    resources = {resource["name"]: resource for resource in package["resources"]}
    assert len(resources) == 28
    for table in TABLES:
        for name, path in ((table.name, f"{table.name}.jsonl"), (f"{table.name}-csv", f"{table.name}.csv")):
            resource = resources[name]
            assert resource["path"] == path
            assert [field["name"] for field in resource["schema"]["fields"]] == list(table.names())
            assert resource["hash"] == f"sha256:{sha256_of(built.files[path])}"
            assert resource["bytes"] == len(built.files[path])
    keys = resources["citations"]["schema"]["foreignKeys"]
    assert {"fields": "claim_id", "reference": {"resource": "claims", "fields": "id"}} in keys


def test_the_readme_and_citation_file_name_both_dois_and_the_licence() -> None:
    built = release_files(empty_tables(), STAMP, NO_CHANGES, site=SITE)
    readme = built.files["README.md"].decode("utf-8")
    cff = built.files["CITATION.cff"].decode("utf-8")
    assert "https://doi.org/10.5072/zenodo.200" in readme
    assert "https://doi.org/10.5072/zenodo.199" in readme
    assert "CC BY 4.0" in readme
    assert "keep their own licences" in readme
    assert 'doi: "10.5072/zenodo.200"' in cff
    assert 'value: "10.5072/zenodo.199"' in cff
    assert "license: CC-BY-4.0" in cff
    assert 'date-released: "2026-11-21"' in cff
    assert (
        built.files["CHANGES.md"].decode("utf-8")
        == "# Changes in version 2026.11.21\n\nThis is the first release.\n"
    )


def test_a_release_folder_is_taken_only_when_every_file_matches_its_manifest() -> None:
    built = release_files(
        tables_with(families=[family_row("Embroidery", "Embroidery", 2)]), STAMP, NO_CHANGES, site=SITE
    )
    folder = release_folder(built.files)
    assert (folder.version, folder.doi) == ("2026.11.21", "10.5072/zenodo.200")
    assert folder.counts["families"] == 1 and folder.counts["claims"] == 0
    with pytest.raises(InvalidInput, match="do not match"):
        release_folder({**built.files, "families.csv": b"slug\n"})
    with pytest.raises(InvalidInput, match="holds no"):
        release_folder({name: body for name, body in built.files.items() if name != "SHA256SUMS"})
