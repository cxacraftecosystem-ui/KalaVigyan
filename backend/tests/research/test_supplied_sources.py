import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.research.evidence import EvidenceItem
from app.research.quotes import quote_occurs
from app.research.supplied_sources import (
    PASSAGE_SEPARATOR,
    SourceAccess,
    SourceIdentity,
    SuppliedPassage,
    SupplySource,
    cite_key,
    cite_url,
    isbn13,
    matching_work,
    normal_doi,
    supplied_grade,
    supplied_note,
    supplied_text,
)

RETRIEVED = datetime(2026, 11, 21, 9, tzinfo=UTC)
TITLE = "Mordant printing with alum and madder in Kachchh"
ACCESS = {"how": "SUBSCRIPTION", "accessedOn": "2026-11-20"}
PASSAGE = {"text": "Alum is printed before the madder bath so the red fixes only there.", "locator": "p. 14"}


def identity(**changes: Any) -> SourceIdentity:
    return SourceIdentity.model_validate({"title": TITLE, "doi": "10.1000/Kv.42", **changes})


def item(**changes: Any) -> EvidenceItem:
    body: dict[str, Any] = {
        "id": "openalex:W1",
        "adapter": "openalex",
        "tier": "T3",
        "source_type": "PAPER",
        "url": "https://doi.org/10.1000/kv.42",
        "title": TITLE,
        "authors": ["Meera Shah"],
        "published": "2019",
        "retrieved_at": RETRIEVED,
        "trust": "A",
        "doi": "10.1000/kv.42",
    }
    return EvidenceItem.model_validate(body | changes)


def test_an_isbn_ten_becomes_its_isbn_thirteen_and_a_wrong_check_digit_is_refused() -> None:
    assert isbn13("0-306-40615-2") == "9780306406157"
    assert isbn13("978-0-306-40615-7") == "9780306406157"
    with pytest.raises(ValueError, match="check digit"):
        isbn13("0-306-40615-3")
    with pytest.raises(ValueError, match="check digit"):
        isbn13("9780306406158")
    with pytest.raises(ValueError, match="10 or 13 digits"):
        isbn13("12345")


def test_a_doi_loses_its_resolver_and_its_case() -> None:
    assert normal_doi("https://doi.org/10.1000/Kv.42") == "10.1000/kv.42"
    assert normal_doi("doi:10.1000/ABC") == "10.1000/abc"
    with pytest.raises(ValueError, match=r"starts 10."):
        normal_doi("11.1000/abc")


def test_a_source_is_identified_by_its_doi_isbn_or_address() -> None:
    with pytest.raises(ValidationError, match="identified by its DOI"):
        SourceIdentity.model_validate({"title": TITLE})
    assert identity(isbn="0306406152").isbn == "9780306406157"


def test_the_cite_url_prefers_the_doi_then_the_address_then_the_isbn() -> None:
    assert cite_url(identity()) == "https://doi.org/10.1000/kv.42"
    by_url = identity(doi=None, url="https://Archive.example.org/ajrakh/")
    assert cite_url(by_url) == "https://archive.example.org/ajrakh"
    assert cite_url(by_url, "10.5555/X1") == "https://doi.org/10.5555/x1"
    by_isbn = identity(doi=None, isbn="0306406152")
    assert cite_url(by_isbn) == "https://openlibrary.org/isbn/9780306406157"
    assert cite_key("https://DOI.org/10.1000/KV.42/") == "https://doi.org/10.1000/kv.42"


@pytest.mark.parametrize(
    ("declared", "found", "grade"),
    [
        ({}, item(), "A"),
        ({"authors": []}, item(trust="B", authors=[]), "C"),
        ({"authors": ["Meera Shah"]}, item(trust="B"), "B"),
        ({"authors": ["Meera Shah"]}, None, "C"),
        ({"authors": [], "publisher": "Khamir"}, None, "C"),
        ({"authors": []}, None, "D"),
    ],
)
def test_the_grade_follows_the_rubric(
    declared: dict[str, Any], found: EvidenceItem | None, grade: str
) -> None:
    assert supplied_grade(identity(**declared), found)[0] == grade


def test_a_confirmed_work_says_where_it_was_found() -> None:
    assert supplied_grade(identity(), item())[1] == "found in openalex as paper, graded A"


def test_a_doi_is_matched_only_by_the_same_doi() -> None:
    assert matching_work(identity(), [item(doi="10.1000/other"), item()]) == item()
    assert matching_work(identity(doi="10.1000/missing"), [item()]) is None


@pytest.mark.parametrize(
    ("declared", "found", "matches"),
    [
        ({"year": 2019, "authors": ["M. Shah"]}, {}, True),
        ({"year": 2020}, {}, True),
        ({"year": 2021}, {}, False),
        ({"authors": ["Asha Rao"]}, {}, False),
        ({"title": "Mordant printing with alum"}, {}, True),
        ({"title": "Mordant printing"}, {}, False),
        ({"title": "Indigo vats of Bagru"}, {}, False),
    ],
)
def test_without_a_doi_the_title_year_and_an_author_match(
    declared: dict[str, Any], found: dict[str, Any], matches: bool
) -> None:
    wanted = identity(doi=None, url="https://example.org/paper", **declared)
    assert (matching_work(wanted, [item(**found)]) is not None) == matches


def test_the_words_come_one_way_only() -> None:
    base = {"identity": {"title": TITLE, "doi": "10.1000/kv.42"}, "access": ACCESS}
    assert len(SupplySource.model_validate({**base, "passages": [PASSAGE]}).passages) == 1
    for wrong in ({}, {"passages": [PASSAGE], "upload": "pdf"}, {"passages": [PASSAGE, PASSAGE]}):
        with pytest.raises(ValidationError):
            SupplySource.model_validate({**base, **wrong})
    assert SupplySource.model_validate({**base, "upload": "pdf"}).upload == "pdf"


def test_no_quote_spans_two_supplied_passages() -> None:
    first = SuppliedPassage(text="The cloth is washed in the river at dawn.", locator="p. 3")
    second = SuppliedPassage(text="Then it is dried on the sand for a day.", locator="p. 4")
    text = supplied_text([first, second])
    assert text == first.text + PASSAGE_SEPARATOR + second.text
    assert quote_occurs("washed in the river at dawn", text)
    assert not quote_occurs("river at dawn. Then it is dried", text)


def test_the_note_names_how_and_when_the_text_was_read_and_the_supply() -> None:
    supplied = uuid.UUID("0e000000-0000-4000-8000-0000000000a1")
    note = supplied_note(supplied, SourceAccess(how="OWN_COPY", accessed_on=date(2026, 11, 20)))
    assert note == (
        "text supplied by the proposer, read in a copy the proposer holds on 2026-11-20, "
        f"is held privately for reviewers as supplied source {supplied}"
    )
