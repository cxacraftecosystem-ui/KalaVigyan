import json
from collections.abc import Iterator
from typing import Any

from .golden import SHARED
from .phase_b_golden import catalog_dataset, geo_etl_datasets

INTERNAL_WORDS = (
    "Designer Portal",
    "designer-portal",
    "Kaggle adityaradha007",
    "not confirmed",
    "unconfirmed",
)
CREDIT_FIELDS = ("title", "publisher", "licence", "licenceUrl", "attribution", "citation", "url")


def test_no_shared_payload_golden_names_an_internal_system_or_admits_a_gap() -> None:
    found = {
        path.name: [
            word for word in INTERNAL_WORDS if word.casefold() in path.read_text(encoding="utf-8").casefold()
        ]
        for path in sorted(SHARED.glob("*.golden.*"))
    }
    assert {name: words for name, words in found.items() if words} == {}


def dataset_rows(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        if "code" in node and "licence" in node:
            yield node
        for value in node.values():
            yield from dataset_rows(value)
    elif isinstance(node, list):
        for value in node:
            yield from dataset_rows(value)


def test_every_golden_dataset_row_credits_its_dataset_as_the_geo_etl_catalogue_does() -> None:
    codes = set(geo_etl_datasets())
    rows = [
        (path.name, row)
        for path in sorted(SHARED.glob("*.golden.json"))
        for row in dataset_rows(json.loads(path.read_text(encoding="utf-8")))
        if row["code"] in codes
    ]
    drift = {
        (name, row["code"], field)
        for name, row in rows
        for field in CREDIT_FIELDS
        if field in row and row[field] != catalog_dataset(row["code"])[field]
    }
    assert {row["code"] for _, row in rows} >= {"CHELSA_2_1_1981_2010", "DR_DISTRICT_SHAPES", "GHCN_CAMS_T2M"}
    assert drift == set()
