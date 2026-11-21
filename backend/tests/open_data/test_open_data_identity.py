from datetime import date

import pytest

from app.core.errors import InvalidInput
from app.services.open_data_release import ReleaseStamp, checked_doi, released_on
from app.services.open_data_schema import Table
from app.services.open_data_tables import TABLES
from app.services.open_data_text import citation_bibtex, citation_text

from .release_fixtures import STAMP

CITED = (
    "KalaVigyan, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform, IIT Kharagpur. (2026). "
    "KalaVigyan open knowledge (Version 2026.11.21) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.200"
)
BIBTEX = """@misc{kalavigyan_open_knowledge_2026_11_21,
  author = {{KalaVigyan, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform, IIT Kharagpur}},
  title = {KalaVigyan open knowledge},
  year = {2026},
  version = {2026.11.21},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.200},
  url = {https://doi.org/10.5281/zenodo.200}
}"""


def test_a_version_is_its_release_day_with_an_optional_second_number() -> None:
    assert released_on("2026.11.21") == date(2026, 11, 21)
    assert released_on("2026.11.21.2") == date(2026, 11, 21)


@pytest.mark.parametrize("version", ["2026-11-21", "2026.13.01", "2026.02.30", "2026.11.21.0", "v1", ""])
def test_a_version_that_is_not_a_day_is_refused(version: str) -> None:
    with pytest.raises(InvalidInput, match=r"YYYY.MM.DD"):
        released_on(version)


def test_a_doi_is_checked_before_it_reaches_a_file() -> None:
    assert checked_doi("10.5281/zenodo.1234567") == "10.5281/zenodo.1234567"
    for wrong in ("https://doi.org/10.5281/zenodo.1", "zenodo.1", "10.5281/ zenodo"):
        with pytest.raises(InvalidInput, match="not a DOI"):
            checked_doi(wrong)


def test_a_stamp_refuses_an_unknown_target_and_a_record_id_below_one() -> None:
    with pytest.raises(InvalidInput, match="SANDBOX or ZENODO"):
        ReleaseStamp("ZENODO_TEST", "2026.11.21", "10.5281/zenodo.2", "10.5281/zenodo.1", 2, 1)
    with pytest.raises(InvalidInput, match="positive"):
        ReleaseStamp("ZENODO", "2026.11.21", "10.5281/zenodo.2", "10.5281/zenodo.1", 0, 1)
    assert STAMP.doi_url() == "https://doi.org/10.5072/zenodo.200"
    assert STAMP.concept_doi_url() == "https://doi.org/10.5072/zenodo.199"


def test_the_citation_names_the_centre_the_version_the_year_and_the_doi() -> None:
    assert citation_text("2026.11.21", date(2026, 11, 21), "10.5281/zenodo.200") == CITED
    assert citation_bibtex("2026.11.21", date(2026, 11, 21), "10.5281/zenodo.200") == BIBTEX


def test_every_table_is_keyed_by_columns_it_always_holds() -> None:
    names = [table.name for table in TABLES]
    assert len(names) == len(set(names)) == 14
    for table in TABLES:
        required = {column.name for column in table.columns if column.required}
        assert set(table.key) <= required, table.name
        assert len(table.names()) == len(set(table.names())), table.name


def _every_column(tables: tuple[Table, ...]) -> set[str]:
    return {column.name for table in tables for column in table.columns}


def test_no_table_carries_a_quote_a_contributor_or_a_private_text() -> None:
    columns = _every_column(TABLES)
    for private in (
        "quote",
        "quotes",
        "created_by",
        "added_by",
        "contributor",
        "reviewer",
        "supplied_text",
        "email",
    ):
        assert private not in columns
