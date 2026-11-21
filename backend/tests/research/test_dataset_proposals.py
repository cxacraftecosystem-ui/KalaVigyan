from typing import Any

import pytest
from pydantic import ValidationError

from app.research.component_specs import checked_spec
from app.research.component_specs_general_delivery import cited_cells, cited_dataset
from app.research.dataset_proposals import (
    ROWS_MAX,
    DatasetProposal,
    TableRefused,
    parsed_table,
    record_problems,
    upload_url,
)

SHA = "a" * 64
RECORD: dict[str, Any] = {
    "code": "KV_TEST_ARTISANS",
    "title": "Artisans by district",
    "publisher": "A state handicrafts department",
    "edition": "2024",
    "version": "1",
    "period": "2024",
    "native_resolution": "district",
    "crs": "none, a table by district",
    "licence": "CC BY 4.0",
    "licence_url": "https://creativecommons.org/licenses/by/4.0/",
    "attribution": "A state handicrafts department",
    "redistributable": True,
    "citation": "A state handicrafts department (2024). Artisans by district. https://doi.org/10.5281/zenodo.1",
    "doi": "10.5281/zenodo.1",
    "landing_url": "https://example.org/artisans",
    "url": "https://example.org/artisans.csv",
    "sha256": SHA,
}
HEAD = {"title": "u0001", "caption": None}


def proposal(**changes: Any) -> DatasetProposal:
    return DatasetProposal.model_validate({**RECORD, **changes})


def test_an_open_redistributable_record_with_its_doi_cited_has_no_problem() -> None:
    assert record_problems(proposal()) == []


def test_a_closed_licence_a_dataset_kept_from_redistribution_and_an_uncited_doi_are_problems() -> None:
    closed = proposal(licence="CC BY-NC 4.0", licence_url="https://creativecommons.org/licenses/by-nc/4.0/")
    assert record_problems(closed)[0].startswith(
        "the licence 'CC BY-NC 4.0' is not one the gates read as open"
    )
    assert record_problems(proposal(redistributable=False)) == [
        "a contributed dataset is one its licence lets anyone redistribute"
    ]
    assert record_problems(proposal(doi="10.5281/zenodo.2")) == [
        "the citation names its DOI 10.5281/zenodo.2"
    ]


def test_a_record_s_code_and_digest_have_their_shapes() -> None:
    with pytest.raises(ValidationError, match="sha256"):
        proposal(sha256="ABC")
    with pytest.raises(ValidationError, match="code"):
        proposal(code="kv-test")


def test_a_table_is_read_with_its_header_and_trimmed_cells() -> None:
    table = parsed_table("﻿district,artisans\n Kachchh , 1200\n\nBidar,640\n".encode())
    assert table.columns == ("district", "artisans")
    assert table.rows == (("Kachchh", "1200"), ("Bidar", "640"))


@pytest.mark.parametrize(
    ("data", "says"),
    [
        (b"", "1 byte"),
        (b"district,artisans\n", "a header row and at least one row"),
        (b"district,district\nA,1\n", "a name of its own"),
        (b"district,artisans\nA\n", "row 1 has 1 cells, and the header names 2 columns"),
        ("district\né".encode("latin-1"), "UTF-8"),
    ],
)
def test_a_table_off_its_rules_is_refused(data: bytes, says: str) -> None:
    with pytest.raises(TableRefused, match=says):
        parsed_table(data)


def test_a_table_holds_at_most_its_rows() -> None:
    lines = "n\n" + "1\n" * (ROWS_MAX + 1)
    with pytest.raises(TableRefused, match=f"1 to {ROWS_MAX} rows"):
        parsed_table(lines.encode())


def test_the_upload_address_is_the_api_s_dataset_slot() -> None:
    assert (
        upload_url("https://api.example.org/", "kvds_x")
        == "https://api.example.org/api/dataset-uploads/kvds_x"
    )


def chart(**changes: Any) -> dict[str, Any]:
    points = [
        {"label": "u0003", "value": 1200, "reading": "u0004", "cell": {"row": 1, "column": "artisans"}},
        {"label": "u0005", "value": 640, "reading": "u0006", "cell": {"row": 2, "column": "artisans"}},
    ]
    body = {
        "head": HEAD,
        "form": "bars",
        "valueLabel": "u0002",
        "series": [{"name": "u0007", "points": points}],
    }
    return {**body, "emphasis": None, "dataset": {"code": "KV_TEST_ARTISANS"}, **changes}


def test_a_chart_names_its_dataset_and_each_value_s_cell() -> None:
    checked = checked_spec("chart", chart())
    cite = cited_dataset(checked)
    assert cite is not None and cite.code == "KV_TEST_ARTISANS"
    cells = cited_cells(checked)
    assert [(cell.cell.row, cell.cell.column, cell.unit, cell.value) for cell in cells] == [
        (1, "artisans", "u0004", 1200),
        (2, "artisans", "u0006", 640),
    ]


def test_cells_and_a_dataset_come_together() -> None:
    with pytest.raises(ValidationError, match="names the dataset too"):
        checked_spec("chart", chart(dataset=None))


def test_a_table_locates_its_cells_by_row_and_column() -> None:
    spec = {
        "head": HEAD,
        "columns": [
            {"label": "u0002", "numeric": False},
            {"label": "u0003", "numeric": True, "column": "artisans"},
        ],
        "rows": [{"cells": ["u0004", "u0005"], "row": 2}],
        "dataset": {"code": "KV_TEST_ARTISANS"},
    }
    cells = cited_cells(checked_spec("fact_table", spec))
    assert [(cell.cell.row, cell.cell.column, cell.unit, cell.value) for cell in cells] == [
        (2, "artisans", "u0005", None)
    ]
