import json

from app.data import craft_master_loader as loader
from app.data.craft_master_catalogue import build_catalogue


def test_vendored_master_has_455_crafts_9_categories_36_sub_categories():
    crafts = loader.load_master()
    assert len(crafts) == loader.MASTER_COUNT == 455
    categories = loader.master_categories()
    assert len(categories) == 9
    assert sum(len(c.sub_categories) for c in categories) == 36
    assert len({c.slug for c in crafts}) == 455
    assert len({c.source_serial for c in crafts}) == 455
    assert sum(1 for c in crafts if c.is_catch_all) == 35


def test_recorded_sha1_matches_vendored_file():
    assert loader.recorded_sha1() == loader.master_sha1()
    assert loader.master_is_current()


def test_master_id_is_stable_and_matches_designer_portal_shape():
    assert loader.master_id("c", "Kutch-Ajrakh") == loader.master_id("c", "Kutch-Ajrakh")
    assert loader.master_id("c", "Kutch-Ajrakh").startswith("cmc")
    assert len(loader.master_id("k", "x")) == 25
    import uuid

    assert uuid.UUID(loader.seed_uuid("c", "Kutch-Ajrakh")).version == 5
    assert loader.seed_uuid("c", "Kutch-Ajrakh") != loader.seed_uuid("s", "Kutch-Ajrakh")


def test_seed_plan_rows_reference_each_other():
    plan = loader.seed_plan(aliases={"crafts": {}})
    category_ids = {row["id"] for row in plan["categories"]}
    sub_ids = {row["id"] for row in plan["subCategories"]}
    assert all(row["categoryId"] in category_ids for row in plan["subCategories"])
    assert all(row["subCategoryId"] in sub_ids for row in plan["crafts"])
    codes = {row["code"] for row in plan["codes"]}
    assert all(row["craftCode"] in codes for row in plan["spellings"])
    assert all(row["craftCode"] in codes for row in plan["crafts"] if row["craftCode"])
    assert len({row["spelling"] for row in plan["spellings"]}) == len(plan["spellings"])
    craft = next(row for row in plan["crafts"] if row["slug"] == "Bidriware")
    assert craft["craftCode"] == "bidriware"
    assert craft["extraMetadata"][loader.MASTER_SEED_KEY]["sourceSerial"] == craft["sourceSerial"]


def test_seed_plan_carries_aliases_from_the_alias_file():
    aliases = {
        "crafts": {
            "Bidriware": {
                "aliases": [{"alias": "Bidri", "norm": "bidri", "source": "WIKIDATA", "script": "Latn", "lang": "en"}]
            }
        }
    }
    plan = loader.seed_plan(aliases=aliases)
    assert plan["aliases"] == [
        {
            "craftId": loader.seed_uuid("c", "Bidriware"),
            "alias": "Bidri",
            "aliasNorm": "bidri",
            "script": "Latn",
            "lang": "en",
            "source": "WIKIDATA",
            "status": "ACTIVE",
        }
    ]


def test_catalogue_matches_designer_portal_shape():
    catalogue = build_catalogue(aliases={"crafts": {}})
    assert set(catalogue) == {"version", "categories", "crafts"}
    row = catalogue["crafts"][0]
    assert set(row) == {
        "id",
        "slug",
        "name",
        "localName",
        "categoryId",
        "subCategoryId",
        "sourceSerial",
        "stateOfOrigin",
        "stateOfPractice",
        "giStatus",
        "isCatchAll",
        "craftCode",
        "aliases",
    }
    assert sum(sub["craftCount"] for cat in catalogue["categories"] for sub in cat["subCategories"]) == 455
    assert catalogue == build_catalogue(aliases={"crafts": {}})


def test_craft_aliases_reads_extra_metadata_like_designer_portal():
    assert loader.craft_aliases({"extraMetadata": json.dumps({"aliases": ["A", " ", "B"]})}) == ["A", "B"]
    assert loader.craft_aliases({"extraMetadata": "not json"}) == []
    meta = loader.with_alias({"aliases": ["Bagru"]}, "bagru")
    assert meta["aliases"] == ["Bagru"]


def test_generated_files_are_valid_when_present():
    for path in (loader.CRAFT_ALIASES_FILE, loader.CRAFT_WIKIDATA_FILE, loader.SEED_CLAIMS_FILE):
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["version"] == 1
    if loader.CRAFT_WIKIDATA_FILE.exists():
        data = json.loads(loader.CRAFT_WIKIDATA_FILE.read_text(encoding="utf-8"))
        assert len(data["crafts"]) == 455
        for row in data["crafts"]:
            assert row["status"] in {"MATCHED", "LOW_CONFIDENCE", "NO_MATCH", "CATCH_ALL"}
            if row["status"] != "MATCHED":
                assert row["match"] is None
    if loader.CRAFT_ALIASES_FILE.exists():
        data = json.loads(loader.CRAFT_ALIASES_FILE.read_text(encoding="utf-8"))
        assert set(data["crafts"]) == {c.slug for c in loader.load_master()}
