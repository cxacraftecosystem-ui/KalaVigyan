import asyncio
from dataclasses import dataclass, field

from app.planner.failures import FailureLog
from app.planner.orchestrator import ResearchPlanner
from app.planner.reading import DocumentReader, LiveSources, ReadCache
from app.research.evidence import SourceDocument
from app.research.evidence_pack import PackedEvidence

from .fakes import FakeAdapter, FakeRetriever, model_for, request, scholarly, web_page

W1 = scholarly("W1", doi=None)
W2 = scholarly("W2", doi=None, trust="B")
P1 = web_page("p1")
ENTRY = PackedEvidence(item=W1, facet_indexes=(0,), found_by=("openalex",), hits=1, best_rank=1)


@dataclass
class ReadReports:
    ids: list[str] = field(default_factory=list)

    async def __call__(self, document: SourceDocument) -> None:
        self.ids.append(document.item.id)


def openalex(*, readable: bool = True) -> FakeAdapter:
    texts = {W1.id: "Alum binds alizarin to cotton."} if readable else {}
    return FakeAdapter("openalex", "T3", [W1, W2], texts=texts)


def reader(
    adapter: FakeAdapter, *, reads: ReadCache | None = None, reports: ReadReports | None = None
) -> DocumentReader:
    sources = LiveSources(searchers=(adapter,))
    return DocumentReader(sources, mode="HYBRID", log=FailureLog(), on_read=reports, reads=reads)


async def test_two_readers_sharing_a_cache_fetch_a_document_once_and_report_it_once() -> None:
    adapter, cache, reports = openalex(), ReadCache(), ReadReports()
    first = await reader(adapter, reads=cache, reports=reports).read(ENTRY)
    second = await reader(adapter, reads=cache, reports=reports).read(ENTRY)
    assert adapter.fetched == [W1.id]
    assert first is not None and first is second
    assert first.item.id == W1.id
    assert reports.ids == [W1.id]


async def test_two_readers_asking_for_one_document_at_once_fetch_it_once() -> None:
    adapter, cache = openalex(), ReadCache()
    first, second = await asyncio.gather(
        reader(adapter, reads=cache).read(ENTRY), reader(adapter, reads=cache).read(ENTRY)
    )
    assert adapter.fetched == [W1.id]
    assert first is not None and first is second


async def test_a_read_that_found_no_document_is_not_paid_for_twice() -> None:
    adapter, cache, reports = openalex(readable=False), ReadCache(), ReadReports()
    first = await reader(adapter, reads=cache, reports=reports).read(ENTRY)
    second = await reader(adapter, reads=cache, reports=reports).read(ENTRY)
    assert (first, second) == (None, None)
    assert adapter.fetched == [W1.id]
    assert reports.ids == []


async def test_readers_without_a_shared_cache_each_fetch_the_document() -> None:
    adapter = openalex()
    await reader(adapter).read(ENTRY)
    await reader(adapter).read(ENTRY)
    assert adapter.fetched == [W1.id, W1.id]


async def test_two_research_runs_given_one_cache_fetch_each_document_once() -> None:
    scholarly_source = openalex()
    web = FakeAdapter("web", "T4", [P1], texts={P1.id: "P1 page text on mordants."})
    sources = LiveSources(searchers=(scholarly_source, web))
    cache = ReadCache()
    packs = [
        await ResearchPlanner(model=model_for(), retriever=FakeRetriever(), sources=sources).research(
            request(), reads=cache
        )
        for _ in range(2)
    ]
    assert scholarly_source.fetched == [W1.id, W2.id]
    assert web.fetched == [P1.id]
    assert [[document.item.id for document in pack.documents] for pack in packs] == [[W1.id, P1.id]] * 2
