import hashlib

import pytest

from app.core.errors import ExternalFailure
from app.planner.failures import FailureLog
from app.planner.reading import DocumentReader, LiveSources
from app.research.evidence import Quote
from app.research.evidence_pack import PackedEvidence
from app.research.fetcher import FETCH_TEXT_MAX_CHARS
from app.research.storable import storable_text
from app.sources.adapter import build_document
from app.sources.scholarly.core_works import CoreAdapter

from ..planner.fakes import FakeAdapter, FakeFetcher, FakeLocator, scholarly
from ..research.fixtures import evidence_item
from .recorded import Recorder, Reply, fixed_clock, source_http

CORE_WORK = "api.core.ac.uk/v3/works/67302936"
CORE_TEXT = "Indian Journal of Fibre & Textile Research\nVol 44, March 2019, pp. 83-91"
ITEM = evidence_item(
    id="core:4242",
    adapter="core",
    url="https://core.ac.uk/works/4242",
    title="Red clay brick",
    doi=None,
    quotes=[],
)
QUOTED = ITEM.model_copy(update={"quotes": [Quote(text="fired at 950 °C")]})
COPY = "https://repository.example.org/copy.pdf"
DOI = "10.1000/copy"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def core(fixture: str) -> CoreAdapter:
    return CoreAdapter(
        source_http(Recorder({CORE_WORK: Reply(fixture)}), "core"), api_key="core-key", clock=fixed_clock()
    )


async def test_a_core_full_text_with_controls_at_its_ends_is_hashed_as_it_is_stored() -> None:
    document = await core("core_work_controls.json").fetch("core:67302936")
    assert (document.content, document.text) == ("FULL_TEXT", CORE_TEXT)
    assert document.text_sha256 == sha256(CORE_TEXT)


async def test_a_core_full_text_of_controls_alone_gives_way_to_the_abstract() -> None:
    document = await core("core_work_only_controls.json").fetch("core:67302936")
    assert document.content == "ABSTRACT"
    assert document.text.startswith("Cotton fabrics have been treated")


def test_a_text_left_with_space_at_an_end_by_cleaning_or_by_the_cut_is_stored_without_it() -> None:
    assert build_document(ITEM, "\x00 Fired at 950 °C.\x03 ", "FULL_TEXT").text == "Fired at 950 °C."
    cut = build_document(ITEM, "a" * (FETCH_TEXT_MAX_CHARS - 1) + " b", "FULL_TEXT")
    assert (cut.text, cut.truncated) == ("a" * (FETCH_TEXT_MAX_CHARS - 1), True)
    assert cut.text_sha256 == sha256(cut.text)


def test_a_lone_surrogate_never_reaches_the_store() -> None:
    assert storable_text("Fired\ud83d at 950 °C.") == "Fired at 950 °C."
    assert build_document(ITEM, "Fired\udc00 at 950 °C.", "FULL_TEXT").text == "Fired at 950 °C."


def test_a_document_that_cannot_be_built_is_an_external_failure_naming_its_item() -> None:
    for text, item in (("\x00\x03 \x1b", ITEM), ("Bricks were fired in a kiln.", QUOTED)):
        with pytest.raises(ExternalFailure) as failure:
            build_document(item, text, "FULL_TEXT")
        assert (failure.value.service, failure.value.kind) == ("core", "error")
        assert str(failure.value).startswith("core:4242 gives no usable document: ")


async def test_a_source_whose_document_cannot_be_built_is_skipped_and_logged() -> None:
    work = scholarly("W1", doi=None)
    entry = PackedEvidence(item=work, facet_indexes=(0,), found_by=("openalex",), hits=1, best_rank=1)
    log = FailureLog()
    adapter = FakeAdapter("openalex", "T3", [work], texts={work.id: "\x00 \x03"})
    reader = DocumentReader(LiveSources(searchers=(adapter,)), mode="HYBRID", log=log)
    assert await reader.read(entry) is None
    (failure,) = log.failures
    assert (failure.stage, failure.service, failure.target, failure.kind) == (
        "FETCH",
        "openalex",
        work.id,
        "error",
    )


async def test_an_open_copy_whose_document_cannot_be_built_is_skipped_and_logged() -> None:
    log = FailureLog()
    sources = LiveSources(
        searchers=(FakeAdapter("crossref", "T3"),),
        fetcher=FakeFetcher({COPY: "\x00\x03"}),
        locator=FakeLocator({DOI: COPY}),
    )
    reader = DocumentReader(sources, mode="DEEP", log=log)
    assert await reader.open_access_document(scholarly("copy", doi=DOI, adapter="crossref")) is None
    assert [(failure.stage, failure.target) for failure in log.failures] == [("FETCH", COPY)]
