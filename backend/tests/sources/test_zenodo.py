import logging

import pytest

from app.core.errors import ExternalFailure, InvalidInput
from app.research.evidence import OpenAccessLocator, SearchQuery, SourceAdapter
from app.sources.scholarly.open_copies import OpenCopyLocator
from app.sources.scholarly.unpaywall import UnpaywallLocator
from app.sources.scholarly.zenodo import ZENODO_LIMITS, ZenodoAdapter, ZenodoLocator

from .recorded import CONTACT, RETRIEVED, Recorder, Reply, fixed_clock, source_http

RECORDS = "zenodo.org/api/records"
RECORD = "zenodo.org/api/records/7694966"
PDF = "https://zenodo.org/api/records/7694966/files/2.pdf/content"


def adapter(routes: dict) -> tuple[ZenodoAdapter, Recorder]:
    recorder = Recorder(routes)
    return ZenodoAdapter(source_http(recorder, "zenodo"), clock=fixed_clock()), recorder


def locator(routes: dict) -> tuple[ZenodoLocator, Recorder]:
    recorder = Recorder(routes)
    return ZenodoLocator(source_http(recorder, "zenodo"), clock=fixed_clock()), recorder


async def test_zenodo_search_asks_with_words_only_and_at_most_25_results() -> None:
    search, recorder = adapter({RECORDS: Reply("zenodo_search.json")})
    items = await search.search(SearchQuery(text="alizarin: mordant (cotton)"), 30)
    assert [item.id for item in items] == ["zenodo:2669693", "zenodo:7694966", "zenodo:21735698"]
    sent = recorder.requests[0].url.params
    assert (sent["q"], sent["size"]) == ("alizarin mordant cotton", "25")


async def test_zenodo_records_are_repository_copies_under_their_own_licence() -> None:
    search, _ = adapter({RECORDS: Reply("zenodo_search.json")})
    lesson, article, _ = await search.search(SearchQuery(text="alizarin mordant cotton"), 3)
    assert (lesson.source_type, lesson.trust, lesson.licence, lesson.publisher) == (
        "OTHER",
        "C",
        "other-open",
        "Zenodo",
    )
    assert (lesson.authors, lesson.published) == (["jamie jamison"], "2019-05-01")
    assert (article.doi, article.url) == ("10.5281/zenodo.7694966", "https://doi.org/10.5281/zenodo.7694966")
    assert (article.source_type, article.trust, article.tier) == ("PAPER", "B", "T3")
    assert (article.authors, article.published) == (["Ozan Deveoglu *"], "2023-03-03")
    assert article.licence == "cc-by-4.0"
    assert article.publisher == "INTERNATIONAL JOURNAL OF ENGINEERING SCIENCES & RESEARCH TECHNOLOGY"
    assert article.external_ids == {"zenodo": "7694966"}
    assert article.retrieved_at == RETRIEVED


@pytest.mark.parametrize(
    ("resource_type", "kind"),
    [
        ({"type": "publication", "subtype": "preprint"}, ("PAPER", "B")),
        ({"type": "publication", "subtype": "thesis"}, ("OTHER", "B")),
        ({"type": "publication", "subtype": "technicalnote"}, ("OTHER", "B")),
        ({"type": "dataset"}, ("DATASET", "B")),
        ({"type": "poster"}, ("OTHER", "C")),
        ({}, ("OTHER", "C")),
    ],
)
def test_zenodo_resource_types_map_onto_the_trust_table(resource_type: dict, kind: tuple[str, str]) -> None:
    search, _ = adapter({})
    record = {"id": 7, "metadata": {"title": "A record", "resource_type": resource_type}}
    (item,) = search._usable_items([record], RETRIEVED)
    assert (item.source_type, item.trust) == kind
    assert (item.url, item.doi) == ("https://zenodo.org/records/7", None)


def test_a_hit_without_a_numeric_id_is_left_out_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    search, _ = adapter({})
    with caplog.at_level(logging.WARNING):
        items = search._usable_items([{"id": "7694966", "metadata": {"title": "A record"}}], RETRIEVED)
    assert items == []
    assert "zenodo left out result 0: no Zenodo record id" in caplog.text


async def test_a_query_without_words_asks_nothing() -> None:
    search, recorder = adapter({})
    assert await search.search(SearchQuery(text="::"), 5) == []
    assert recorder.requests == []


async def test_zenodo_fetch_returns_the_record_description() -> None:
    reader, recorder = adapter({RECORD: Reply("zenodo_record.json")})
    document = await reader.fetch("zenodo:7694966")
    assert document.content == "ABSTRACT"
    assert document.text.startswith(
        "This study aimed at investigating organic cotton fabrics dyed with five different percentages "
        "(5 %, 10 %, 20 %, 40 % and 80 %) of the roots of madder (Rubia tinctorum L.) via the shellacs of "
        "gall oak (Quercus infectoria Olivier; 1 %, 2%, 4%, 8 %, 16 %) mordant."
    )
    assert "colour coordinates L*, a*, b*, C*, h, K/S and ∆E* values were determined." in document.text
    assert document.text.endswith("was taken by a scanning electron microscope (SEM).")
    assert recorder.requests[0].url.path == "/api/records/7694966"
    with pytest.raises(ExternalFailure) as missing:
        await reader.fetch("zenodo:not-a-number")
    assert missing.value.kind == "not_found"


def test_zenodo_is_a_source_adapter_paced_under_its_search_limit() -> None:
    search, _ = adapter({})
    assert isinstance(search, SourceAdapter)
    assert ZENODO_LIMITS.search.interval == pytest.approx(2.5)


async def test_an_open_record_under_an_open_licence_offers_its_pdf() -> None:
    finder, _ = locator({RECORD: Reply("zenodo_record.json")})
    found = await finder.locate("https://doi.org/10.5281/zenodo.7694966")
    assert (found.doi, found.status, found.is_open) == ("10.5281/zenodo.7694966", "GREEN", True)
    assert (found.pdf_url, found.landing_url) == (PDF, "https://zenodo.org/records/7694966")
    assert (found.licence, found.host_type, found.version) == ("cc-by-4.0", "REPOSITORY", None)
    assert found.checked_at == RETRIEVED


async def test_an_open_record_under_a_non_commercial_licence_offers_no_file() -> None:
    finder, _ = locator({"zenodo.org/api/records/3339065": Reply("zenodo_record_closed_licence.json")})
    found = await finder.locate("10.5281/zenodo.3339065")
    assert (found.status, found.pdf_url, found.landing_url) == ("GREEN", None, None)
    assert found.licence == "cc-by-nc-nd-1.0"


async def test_a_restricted_record_is_closed() -> None:
    finder, _ = locator({"zenodo.org/api/records/10486092": Reply("zenodo_record_restricted.json")})
    found = await finder.locate("10.5281/zenodo.10486092")
    assert (found.status, found.is_open, found.pdf_url, found.host_type) == ("CLOSED", False, None, None)


async def test_a_concept_doi_is_found_through_its_latest_version() -> None:
    moved = Reply("zenodo_concept_moved.html", status=302, headers={"location": "/api/records/7694966"})
    finder, recorder = locator(
        {"zenodo.org/api/records/7694965": moved, RECORDS: Reply("zenodo_concept_search.json")}
    )
    found = await finder.locate("10.5281/zenodo.7694965")
    assert (found.doi, found.pdf_url) == ("10.5281/zenodo.7694965", PDF)
    sent = recorder.requests[1].url.params
    assert (sent["q"], sent["size"]) == ("conceptrecid:7694965", "1")


async def test_the_zenodo_locator_refuses_a_doi_zenodo_did_not_mint() -> None:
    finder, recorder = locator({})
    with pytest.raises(InvalidInput):
        await finder.locate("10.1038/s41598-022-27110-0")
    assert recorder.requests == []


async def test_open_copies_of_zenodo_dois_are_asked_of_zenodo_and_the_rest_of_unpaywall() -> None:
    recorder = Recorder(
        {
            RECORD: Reply("zenodo_record.json"),
            "api.unpaywall.org/v2/10.1038/s41598-022-27110-0": Reply("unpaywall_open.json"),
        }
    )
    unpaywall = UnpaywallLocator(
        source_http(recorder, "unpaywall"), contact_email=CONTACT, clock=fixed_clock()
    )
    zenodo = ZenodoLocator(source_http(recorder, "zenodo"), clock=fixed_clock())
    finder = OpenCopyLocator(unpaywall, zenodo)
    assert isinstance(finder, OpenAccessLocator)
    assert finder.name == "open_access"
    assert (await finder.locate("10.5281/zenodo.7694966")).pdf_url == PDF
    assert (await finder.locate("10.1038/s41598-022-27110-0")).status == "GOLD"
    assert [request.url.host for request in recorder.requests] == ["zenodo.org", "api.unpaywall.org"]
