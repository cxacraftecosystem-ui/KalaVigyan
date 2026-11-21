import json
from pathlib import Path

import pytest

from app.data.dataset_registry import REGISTRY_PATH, registry_rows
from app.research.datasets import DATASET_BUILDS, DatasetEntry
from app.services.dataset_registry import dataset_registry, entry_columns, registry_entries

REPO = Path(__file__).resolve().parents[3]
LAYERS = REPO / "frontend" / "public" / "layers"
CC0 = "https://creativecommons.org/publicdomain/zero/1.0/"
RECORD_FIELDS = (
    "code",
    "title",
    "publisher",
    "edition",
    "version",
    "period",
    "nativeResolution",
    "crs",
    "licence",
    "licenceUrl",
    "attribution",
    "redistributable",
    "citation",
    "doi",
    "landingUrl",
)


def test_every_dataset_has_one_record_of_one_shape() -> None:
    entries = registry_entries(registry_rows())
    assert len({entry.code for entry in entries}) == len(entries) == 13
    assert {entry.build for entry in entries} == set(DATASET_BUILDS) - {"contributed"}
    assert all(entry.landing_url and entry.crs and entry.version for entry in entries)


def test_a_dataset_recorded_twice_is_refused() -> None:
    row = registry_rows()[0]
    with pytest.raises(ValueError, match="once"):
        registry_entries([row, row])


def test_chelsa_is_credited_under_its_own_licence_not_its_paper() -> None:
    chelsa = dataset_registry()["CHELSA_2_1_1981_2010"]
    assert (chelsa.licence, chelsa.licence_url, chelsa.redistributable) == ("CC0 1.0", CC0, True)
    assert chelsa.doi == "10.16904/envidat.228" and chelsa.doi in (chelsa.citation or "")


def test_the_mineral_deposits_are_one_record_shared_by_both_builds() -> None:
    body = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert [entry["code"] for entry in body["datasets"]].count("USGS_MRDS") == 1
    minerals = json.loads((LAYERS / "minerals.json").read_text(encoding="utf-8"))
    assert minerals["source"]["code"] == "USGS_MRDS"


@pytest.mark.parametrize("name", ["rivers.json", "relief.json", "minerals.json"])
def test_each_physical_layer_carries_its_dataset_s_whole_record(name: str) -> None:
    body = json.loads((LAYERS / name).read_text(encoding="utf-8"))
    rows = body.get("datasets") or [body["source"]]
    registry = dataset_registry()
    for row in rows:
        entry = registry[row["code"]]
        assert set(RECORD_FIELDS) | {"file", "url", "readOn", "sha256"} == set(row)
        assert (row["licence"], row["landingUrl"], row["crs"]) == (
            entry.licence,
            entry.landing_url,
            entry.crs,
        )
        assert len(row["sha256"]) == 64 and len(row["readOn"]) == len("2026-11-20")


def test_a_row_s_columns_are_the_record_s_fields() -> None:
    entry = DatasetEntry.model_validate(registry_rows()[1])
    columns = entry_columns(entry)
    assert (
        columns["landingUrl"] == entry.landing_url and columns["nativeResolution"] == entry.native_resolution
    )
    assert set(columns) == set(RECORD_FIELDS) - {"code"} | {"url"}
