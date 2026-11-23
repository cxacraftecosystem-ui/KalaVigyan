from app.planner.failures import FailureLog
from app.planner.reading import DocumentReader, LiveSources
from app.sources.scholarly.publishers import PublisherFullText

from ..sources.recorded import Reply
from ..sources.test_publisher_full_text import (
    ELSEVIER_ARTICLE,
    ELSEVIER_DOI,
    ELSEVIER_TEXT,
    UNPAYWALL,
    paper,
    publisher,
)
from .fakes import FakeAdapter, FakeFetcher, FakeLocator

HELD_ROUTES = {
    f"{UNPAYWALL}{ELSEVIER_DOI}": Reply("unpaywall_closed.json"),
    ELSEVIER_ARTICLE: Reply("elsevier_article.synthetic.xml"),
}
UNHELD_DOI = "10.1111/cote.12288"


def deep_reader(held: PublisherFullText | None, fetcher: FakeFetcher, locator: FakeLocator) -> DocumentReader:
    sources = LiveSources(
        searchers=(FakeAdapter("crossref", "T3"),), fetcher=fetcher, locator=locator, publisher=held
    )
    return DocumentReader(sources, mode="DEEP", log=FailureLog())


async def test_a_closed_doi_the_publisher_holds_is_read_from_the_publisher() -> None:
    held, recorder = publisher(HELD_ROUTES)
    fetcher, locator = FakeFetcher(), FakeLocator()
    document = await deep_reader(held, fetcher, locator).open_access_document(paper(ELSEVIER_DOI))
    assert document is not None
    assert (document.content, document.text) == ("FULL_TEXT", ELSEVIER_TEXT)
    assert document.item.external_ids["full_text_from"] == "elsevier"
    assert locator.asked == [ELSEVIER_DOI]
    assert fetcher.requests == []
    assert [request.url.path for request in recorder.requests][-1] == f"/content/article/doi/{ELSEVIER_DOI}"


async def test_a_closed_doi_no_publisher_holds_is_not_read() -> None:
    held, recorder = publisher(HELD_ROUTES)
    reader = deep_reader(held, FakeFetcher(), FakeLocator())
    assert await reader.open_access_document(paper(UNHELD_DOI)) is None
    assert recorder.requests == []


async def test_without_a_publisher_a_closed_doi_is_not_read() -> None:
    reader = deep_reader(None, FakeFetcher(), FakeLocator())
    assert await reader.open_access_document(paper(ELSEVIER_DOI)) is None


async def test_an_open_copy_is_still_read_through_the_fetcher_before_any_publisher() -> None:
    held, recorder = publisher(HELD_ROUTES)
    copy = "https://repository.example.org/copy.pdf"
    fetcher = FakeFetcher({copy: "Alum binds alizarin in the open copy."})
    reader = deep_reader(held, fetcher, FakeLocator({ELSEVIER_DOI: copy}))
    document = await reader.open_access_document(paper(ELSEVIER_DOI))
    assert document is not None and document.text == "Alum binds alizarin in the open copy."
    assert recorder.requests == []
