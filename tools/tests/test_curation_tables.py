from __future__ import annotations

import pytest
from app.curation.matching import match_key, quote_found
from app.fetcher.extract import extract
from app.research.quotes import normalise_quote_lines
from app.research.untrusted import clean_untrusted_text
from curation_support import SOURCES, fetched

from curation.reading import source_text
from curation.tables import missing_table_rows, table_rows, with_table_rows

LIVE = "https://example.org/test/registry"
DOCUMENT_ROWS = [
    "| Sl.No. | Document | Date | Download |",
    "| 1 | 9001 - Reply to Formality Check Report by Applicant - 25-12-2025 | 25-12-2025 | |",
    "| 2 | 9001 - Formality Check Report - 21-10-2025 | 21-10-2025 | |",
    "| 3 | 9001 - Statement of Case of the resist print - 15-10-2025 | 15-10-2025 | |",
    "| 4 | 9001 - Form GI-1 of the resist print - 15-10-2025 | 15-10-2025 | |",
]
TWO_ROWS = b"<table><tr><td>Class</td><td>16</td></tr><tr><td>Goods</td><td>Handicraft</td></tr></table>"
LAYOUT_PAGE = (
    "<html><body><table><tr><td><a href='/'>Home</a></td><td>"
    "<p>The resist paste of lime and gum is pressed onto the cloth with a carved block, and the printed "
    "areas stay pale when the cloth goes into the indigo vat.</p>"
    "<p>After the indigo bath the cloth is washed in running water, which removes the paste and shows the "
    "pattern in pale lines on a deep blue ground.</p></td></tr></table></body></html>"
)


def before(body: bytes) -> str:
    page = extract(LIVE, "text/html", body, "utf-8")
    return "\n".join(normalise_quote_lines(clean_untrusted_text(page.text)))


@pytest.mark.parametrize(
    "body",
    [
        (SOURCES / "resist-article.html").read_bytes(),
        LAYOUT_PAGE.encode(),
        LAYOUT_PAGE.replace("<td><a href='/'>Home</a></td>", "").encode(),
    ],
)
def test_a_page_without_a_data_table_reads_exactly_as_before(body: bytes) -> None:
    assert source_text(fetched(LIVE, body, "text/html")) == ("text/html", before(body), False)


def test_a_table_the_main_extraction_left_out_is_added_row_by_row() -> None:
    body = (SOURCES / "registry-details.html").read_bytes()
    _, text, truncated = source_text(fetched(LIVE, body, "text/html"))
    lines = text.split("\n")
    assert not truncated
    assert lines[: -len(DOCUMENT_ROWS)] == before(body).split("\n")
    assert lines[-len(DOCUMENT_ROWS) :] == DOCUMENT_ROWS
    assert lines.count("| Status | Pre Examination |") == 1
    assert "hidden registry row" not in text
    key = match_key(text)
    for quote in (
        "Applicant Name | Test Printers Cooperative Society, Department of Test Crafts",
        "Date of Filing | 05-05-2025",
        "9001 - Statement of Case of the resist print - 15-10-2025 | 15-10-2025",
    ):
        assert quote_found(quote, key)


def test_cells_read_as_the_page_shows_them() -> None:
    body = (
        b"<table><tr><th>Status <!-- internal --></th><td><b>Pre</b> Examination</td></tr>"
        b"<tr><td>Applicant</td><td><p>Test Cooperative</p><p>Society</p></td></tr>"
        b"<tr><td>Area</td><td>Kachchh<br>Gujarat</td></tr>"
        b"<tr><td> </td><td></td></tr></table>"
    )
    assert table_rows(body) == [
        ("Status", "Pre Examination"),
        ("Applicant", "Test Cooperative Society"),
        ("Area", "Kachchh Gujarat"),
    ]


def test_only_innermost_tables_of_two_paired_rows_and_short_cells_are_read() -> None:
    long_cell = "word " * 250
    inner = "<table><tr><td>Class</td><td>16</td></tr><tr><td>Goods</td><td>Handicraft</td></tr></table>"
    body = (
        f"<table><tr><td>{inner}</td><td>outer</td></tr><tr><td>outer</td><td>cells</td></tr></table>"
        "<table><tr><td>a single column</td></tr><tr><td>of notes</td></tr></table>"
        "<table><tr><td>one paired row</td><td>only</td></tr><tr><td>then a note</td></tr></table>"
        f"<table><tr><td>menu</td><td>{long_cell}</td></tr><tr><td>menu</td><td>footer</td></tr></table>"
    ).encode()
    assert table_rows(body) == [("Class", "16"), ("Goods", "Handicraft")]


def test_rows_already_in_the_text_are_not_repeated() -> None:
    body = TWO_ROWS
    assert missing_table_rows(body, "Application\n| Class | 16 |") == ["| Goods | Handicraft |"]
    assert missing_table_rows(body, "| Class | 16 |\n| Goods | Handicraft |") == []
    assert missing_table_rows(body, "Class 160 and Goods") == ["| Class | 16 |", "| Goods | Handicraft |"]


def test_added_rows_keep_the_text_cap() -> None:
    assert with_table_rows(TWO_ROWS, "main text", False, max_chars=1000) == (
        "main text\n| Class | 16 |\n| Goods | Handicraft |",
        False,
    )
    assert with_table_rows(TWO_ROWS, "main text", False, max_chars=12) == ("main text\n| ", True)
    assert with_table_rows(b"<p>no table</p>", "main text", True, max_chars=12) == ("main text", True)
