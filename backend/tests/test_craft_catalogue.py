import json
from typing import Any

import pytest

from app.core.http_cache import etag_matches, quoted_etag
from app.data.craft_master_catalogue import build_catalogue
from app.data.craft_master_loader import MASTER_FILE, seed_plan
from app.data.district_register import REGISTER_FILE
from app.services.craft_catalogue import assemble_catalogue, reference_tables


@pytest.fixture(scope="module")
def plan() -> dict[str, Any]:
    return seed_plan()


def _assemble(plan: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return assemble_catalogue(
        plan["categories"],
        plan["subCategories"],
        plan["crafts"],
        plan["spellings"],
        plan["aliases"],
        **kwargs,
    )


def test_the_catalogue_extends_the_designer_portal_catalogue_field_for_field(plan: dict[str, Any]) -> None:
    live = _assemble(plan)
    files = build_catalogue()
    assert set(files) <= set(live)
    assert set(live) - set(files) == {"schemaVersion", "summary", "concepts"}
    for ours, theirs in zip(live["categories"], files["categories"], strict=True):
        assert {key: ours[key] for key in theirs if key != "subCategories"} == {
            key: value for key, value in theirs.items() if key != "subCategories"
        }
        assert [
            {key: sub[key] for key in theirs["subCategories"][0]} for sub in ours["subCategories"]
        ] == theirs["subCategories"]
    by_id = {row["id"]: row for row in live["crafts"]}
    for row in files["crafts"]:
        shared = {key: value for key, value in row.items() if key != "localName"}
        assert {key: by_id[row["id"]][key] for key in shared} == shared


def test_crafts_follow_category_then_serial_order(plan: dict[str, Any]) -> None:
    live = _assemble(plan)
    place = {
        sub["id"]: (category["sortOrder"], sub["sortOrder"])
        for category in live["categories"]
        for sub in category["subCategories"]
    }
    keys = [(place[c["subCategoryId"]], c["sourceSerial"] or 0) for c in live["crafts"]]
    assert keys == sorted(keys)


def test_version_is_stable_and_moves_on_change(plan: dict[str, Any]) -> None:
    first = _assemble(plan)["version"]
    assert _assemble(plan)["version"] == first
    renamed = [dict(c) for c in plan["crafts"]]
    renamed[0]["name"] = renamed[0]["name"] + " revised"
    moved = assemble_catalogue(
        plan["categories"], plan["subCategories"], renamed, plan["spellings"], plan["aliases"]
    )["version"]
    assert moved != first
    assert _assemble(plan, include_inactive=True)["version"] != first


def test_inactive_crafts_are_hidden_unless_asked(plan: dict[str, Any]) -> None:
    crafts = [dict(c) for c in plan["crafts"]]
    retired = crafts[0]
    retired["status"] = "LEGACY"
    args = (plan["categories"], plan["subCategories"], crafts, plan["spellings"], plan["aliases"])
    active = assemble_catalogue(*args)
    assert retired["id"] not in {c["id"] for c in active["crafts"]}
    assert "status" not in active["crafts"][0]
    full = assemble_catalogue(*args, include_inactive=True, references={retired["id"]: 3})
    assert full["crafts"][-1]["id"] == retired["id"]
    assert full["crafts"][-1]["status"] == "LEGACY"
    assert full["crafts"][-1]["referenceCount"] == 3
    assert full["crafts"][0]["referenceCount"] is None
    total_active = sum(s["craftCount"] for c in full["categories"] for s in c["subCategories"])
    assert total_active == len(crafts) - 1


def test_rejected_aliases_are_left_out(plan: dict[str, Any]) -> None:
    craft = plan["crafts"][0]
    aliases = [{"craftId": craft["id"], "aliasNorm": "zz hidden", "status": "REJECTED"}]
    live = assemble_catalogue(plan["categories"], plan["subCategories"], plan["crafts"], [], aliases)
    assert "zz hidden" not in next(c for c in live["crafts"] if c["id"] == craft["id"])["aliases"]


@pytest.mark.parametrize(
    ("header", "matches"),
    [
        ('"abc"', True),
        ('W/"abc"', True),
        ('"x", "abc"', True),
        ("*", True),
        ('"x"', False),
        (None, False),
        ("", False),
    ],
)
def test_etag_matching(header: str | None, matches: bool) -> None:
    assert etag_matches(header, quoted_etag("abc")) is matches


def test_reference_tables_skip_the_craft_and_its_aliases() -> None:
    names = {table.name for table in reference_tables()}
    assert "CraftAlias" not in names
    assert "Craft" not in names
    assert "CraftLocation" in names


def _master_rows() -> list[dict[str, Any]]:
    return json.loads(MASTER_FILE.read_text(encoding="utf-8"))


def _reader_rows() -> list[dict[str, Any]]:
    return [row for row in _master_rows() if not any("catch-all" in note.lower() for note in row["notes"])]


def test_reader_counts_leave_the_catch_all_rows_listed_but_uncounted(plan: dict[str, Any]) -> None:
    live = _assemble(plan)
    readers = _reader_rows()
    assert len(live["crafts"]) == len(_master_rows()) == 455
    assert live["summary"]["crafts"] == len(readers) == 420
    assert live["summary"]["giRegistered"] == sum(row["giStatus"] == "GI" for row in readers)
    assert (live["summary"]["families"], live["summary"]["kinds"]) == (9, 36)
    hand_block = next(
        sub
        for category in live["categories"]
        for sub in category["subCategories"]
        if sub["slug"] == "Hand-Block-Printing"
    )
    assert (hand_block["craftCount"], hand_block["readerCount"]) == (16, 15)
    textiles = next(category for category in live["categories"] if category["label"] == "Textiles")
    assert textiles["readerCount"] == sum(sub["readerCount"] for sub in textiles["subCategories"])


def test_placed_crafts_and_states_count_only_states_of_india(plan: dict[str, Any]) -> None:
    summary = _assemble(plan)["summary"]
    states = {row["name"] for row in json.loads(REGISTER_FILE.read_text(encoding="utf-8"))["states"]}
    readers = _reader_rows()
    assert summary["placed"] == sum(
        any(state in states for state in row["stateOfPractice"]) for row in readers
    )
    assert summary["states"] == len(
        {state for row in readers for state in row["stateOfPractice"] if state in states}
    )
    assert summary["placed"] < summary["crafts"]


def test_rows_carry_reader_names_family_labels_and_a_palette(plan: dict[str, Any]) -> None:
    rows = {row["slug"]: row for row in _assemble(plan)["crafts"]}
    assert rows["Metal-Embosing"]["displayName"] == "Metal Embossing"
    assert rows["Metal-Embosing"]["name"] == "Metal Embosing"
    assert rows["Other-Hand-Block-Print"]["displayName"] == "Other hand block printing"
    assert rows["Kutch-Ajrakh"]["displayName"] == "Kutch Ajrakh"
    ajrakh = rows["Kutch-Ajrakh"]
    assert (ajrakh["familyLabel"], ajrakh["kindLabel"], ajrakh["palette"]) == (
        "Textiles",
        "Hand block printing",
        "indigo",
    )
    assert rows["Bastar-Dhokra"]["palette"] == "bronze"
    assert ajrakh["hero"] is None and ajrakh["giYear"] is None
    assert ajrakh["depth"] == {"coverage": None, "claims": 0, "stages": 0, "pictures": 0, "places": 0}


def test_a_local_name_is_a_sourced_name_in_the_language_of_the_crafts_state(plan: dict[str, Any]) -> None:
    rows = {row["slug"]: row for row in _assemble(plan)["crafts"]}
    assert rows["Phulkari"]["localName"] == "ਫੁਲਕਾਰੀ"
    assert rows["Kasuti-Embroidery"]["localName"] == "ಕಸೂತಿ"
    assert rows["Assam-Majuli-Manuscript-Painting"]["localName"] is None
    assert rows["Kutch-Ajrakh"]["localName"] is None
    crafts = [dict(row) for row in plan["crafts"]]
    stored = next(row for row in crafts if row["slug"] == "Phulkari")
    stored["localName"] = "ਫੁਲਕਾਰੀ ਕਢਾਈ"
    again = assemble_catalogue(
        plan["categories"], plan["subCategories"], crafts, plan["spellings"], plan["aliases"]
    )
    assert next(row for row in again["crafts"] if row["slug"] == "Phulkari")["localName"] == "ਫੁਲਕਾਰੀ ਕਢਾਈ"
