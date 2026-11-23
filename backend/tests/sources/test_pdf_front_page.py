from app.research.evidence import EvidenceItem
from app.research.fetcher import PageMetadata
from app.services.live_source_store import source_values
from app.sources.web.page import page_item, stated_front

from .jeb_page import CREATED, PAPER_TITLE, STUDY_URL, fetched

JOURNAL = "Journal of Environmental Biology"
AUTHORS = ["Nupur Mathur", "Pradeep Bhatnagar"]
FILE_METADATA = PageMetadata(title="aa.MDI", authors=["sys"], published=CREATED)


def described(item: EvidenceItem) -> tuple[object, ...]:
    return (item.title, item.authors, item.published, item.source_type, item.container_title)


def test_a_pdf_whose_file_names_sys_and_aa_mdi_takes_what_its_first_page_states() -> None:
    item = page_item("proposal", STUDY_URL, fetched(FILE_METADATA))
    assert described(item) == (PAPER_TITLE, AUTHORS, "2007-01", "PAPER", JOURNAL)
    stored = source_values(item)
    assert (stored["title"], stored["authors"], stored["year"], stored["kind"], stored["containerTitle"]) == (
        PAPER_TITLE,
        AUTHORS,
        2007,
        "PAPER",
        JOURNAL,
    )


def test_a_pdf_s_own_authors_and_title_are_kept_and_its_issue_still_dates_it() -> None:
    metadata = PageMetadata(title="Mutagenicity of Sanganer dyes", authors=["N. Mathur"], published=CREATED)
    item = page_item("proposal", STUDY_URL, fetched(metadata))
    assert described(item) == ("Mutagenicity of Sanganer dyes", ["N. Mathur"], "2007-01", "PAPER", JOURNAL)


def test_a_pdf_whose_first_page_states_nothing_drops_the_producer_and_keeps_the_file_date() -> None:
    item = page_item(
        "proposal", STUDY_URL, fetched(FILE_METADATA, text="Notes on dyes\nsome lines of text\n")
    )
    assert described(item) == ("aa.MDI", [], CREATED, "OTHER", None)


def test_an_html_page_is_described_by_its_metadata_alone() -> None:
    page = fetched(FILE_METADATA, content_type="text/html")
    assert stated_front(page) is None
    assert described(page_item("proposal", STUDY_URL, page)) == ("aa.MDI", ["sys"], CREATED, "WEB_PAGE", None)
