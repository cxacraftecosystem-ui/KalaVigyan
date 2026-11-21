import pytest

from app.core.errors import ExternalFailure, NotConfigured
from app.planner.failures import FailureLog
from app.planner.orchestrator import ResearchPlanner
from app.planner.reading import DocumentReader, LiveSources
from app.planner.references import dois_in
from app.research.evidence_pack import EvidencePack, PackedEvidence
from app.research.planning import Planner
from app.sources.web.fallback import WebSearch

from .fakes import (
    FakeAdapter,
    FakeFetcher,
    FakeLocator,
    FakeRetriever,
    claim,
    ids,
    model_for,
    request,
    scholarly,
    web_page,
)

W1 = scholarly("W1", doi="10.1000/a")
W2 = scholarly("W2", doi=None, trust="B")
C1 = scholarly("10.1000/A", doi="10.1000/A", adapter="crossref")
C2 = scholarly("10.1000/c", doi="10.1000/c", adapter="crossref")
P1 = web_page("p1")
P2 = web_page("p2")
OPEN_COPY = "https://repo.example.org/a.pdf"


def planner(
    sources: LiveSources, *, retriever: FakeRetriever | None = None, **model: object
) -> ResearchPlanner:
    return ResearchPlanner(model=model_for(**model), retriever=retriever or FakeRetriever(), sources=sources)


def hybrid_sources() -> tuple[FakeAdapter, FakeAdapter, FakeAdapter]:
    openalex = FakeAdapter("openalex", "T3", [W1, W2], texts={W1.id: "W1 abstract on alum."})
    crossref = FakeAdapter("crossref", "T3", [C1, C2], texts={C2.id: "C2 abstract on alizarin."})
    web = FakeAdapter("web", "T4", [P1, P2], texts={P1.id: "P1 page text on mordants."})
    return openalex, crossref, web


async def test_the_planner_satisfies_the_planner_protocol() -> None:
    assert isinstance(planner(LiveSources(searchers=())), Planner)


async def test_stored_knowledge_that_covers_every_facet_runs_no_live_research() -> None:
    covered = [claim("alum one"), claim("alum two")]
    binding = [claim("binding one"), claim("binding two")]
    retriever = FakeRetriever({"alum": covered, "mordant binding": binding})
    openalex, crossref, web = hybrid_sources()
    pack = await planner(LiveSources(searchers=(openalex, crossref, web)), retriever=retriever).research(
        request()
    )
    assert pack.plan.queries == [] and pack.evidence == () and pack.documents == ()
    assert [entry.covered for entry in pack.coverage] == [True, True]
    assert openalex.searched == crossref.searched == web.searched == []
    assert [(q.text, q.facets, q.limit) for q in retriever.queries] == [
        ("alum", ("MATERIAL",), 10),
        ("mordant binding", ("MECHANISM",), 10),
        ("Why does alum make Ajrakh red last?", (), 20),
    ]


@pytest.mark.parametrize(("focus", "fields"), [("CHEMISTRY", ("CHEMISTRY",)), ("OVERVIEW", ()), (None, ())])
async def test_a_sections_stored_facts_are_searched_in_its_field_unless_it_is_the_overview(
    focus: str | None, fields: tuple[str, ...]
) -> None:
    covered = {
        "alum": [claim("alum one"), claim("alum two")],
        "mordant binding": [claim("b one"), claim("b two")],
    }
    retriever = FakeRetriever(covered)
    await planner(LiveSources(searchers=()), retriever=retriever).research(
        request().model_copy(update={"focus": focus})
    )
    assert [query.fields for query in retriever.queries] == [(), (), fields]


async def test_hybrid_research_dedupes_ranks_and_reads_the_best_per_facet() -> None:
    openalex, crossref, web = hybrid_sources()
    pack = await planner(LiveSources(searchers=(openalex, crossref, web))).research(request())
    assert openalex.searched == [("Ajrakh alum mordant", 5)]
    assert web.searched == [("Kutch Ajrakh alizarin alum lake chemistry", 8)]
    assert ids(pack.evidence) == [W1.id, C2.id, W2.id, P1.id, P2.id]
    lead = pack.evidence[0]
    assert (lead.found_by, lead.hits, lead.best_rank, lead.facet_indexes) == (
        ("openalex", "crossref"),
        2,
        1,
        (0,),
    )
    assert [document.item.id for document in pack.documents] == [W1.id, P1.id, C2.id]
    assert openalex.fetched == [W1.id, W2.id] and web.fetched == [P1.id, P2.id]
    assert [(f.stage, f.service, f.target, f.kind) for f in pack.failures] == [
        ("FETCH", "openalex", W2.id, "not_found"),
        ("FETCH", "web", P2.id, "not_found"),
    ]
    assert EvidencePack.model_validate(pack.model_dump()) == pack


async def test_failed_reads_are_replaced_by_the_next_best_within_the_attempt_cap() -> None:
    pages = [web_page(f"p{n:02d}") for n in range(30)]
    web = FakeAdapter("web", "T4", pages, texts={page.id: "text" for page in pages[12:]})
    ordered = [
        PackedEvidence(item=page, facet_indexes=(0,), found_by=("web",), hits=1, best_rank=n + 1)
        for n, page in enumerate(pages)
    ]
    reader = DocumentReader(LiveSources(searchers=(web,)), mode="HYBRID", log=FailureLog())
    documents = await reader.read_best(ordered, limit=10)
    assert [document.item.id for document in documents] == [page.id for page in pages[12:20]]
    assert web.fetched == [page.id for page in pages[:20]]


async def test_one_failing_source_is_recorded_and_every_source_failing_is_raised() -> None:
    openalex, crossref, web = hybrid_sources()
    crossref.search_failure = ExternalFailure("crossref is down", kind="unavailable", service="crossref")
    pack = await planner(LiveSources(searchers=(openalex, crossref, web))).research(request())
    assert next((f.stage, f.service, f.kind) for f in pack.failures) == ("SEARCH", "crossref", "unavailable")
    for adapter in (openalex, web):
        adapter.search_failure = ExternalFailure("down", kind="rate_limit", service=adapter.name)
    with pytest.raises(ExternalFailure, match="every live search failed"):
        await planner(LiveSources(searchers=(openalex, crossref, web))).research(request())


async def test_a_planned_tier_without_a_source_is_not_configured() -> None:
    openalex, crossref, _ = hybrid_sources()
    with pytest.raises(NotConfigured, match="tier T4"):
        await planner(LiveSources(searchers=(openalex, crossref))).research(request())


async def test_deep_reads_open_access_full_text_and_follows_cited_dois() -> None:
    openalex = FakeAdapter("openalex", "T3", [W1], texts={W1.id: "W1 abstract."})
    web = FakeAdapter("web", "T4", [P1], texts={P1.id: "As in 10.1000/a, see the page."})
    crossref = FakeAdapter("crossref", "T3", texts={"crossref:10.2000/ref.1": "Ref 1 abstract."})
    locator = FakeLocator({"10.1000/a": OPEN_COPY})
    full_text = "Alum binds alizarin (doi:10.2000/ref.1; https://doi.org/10.2000/REF.2.) as 10.1000/a showed."
    fetcher = FakeFetcher({OPEN_COPY: full_text})
    sources = LiveSources(searchers=(openalex, web), fetcher=fetcher, locator=locator, doi_source=crossref)
    pack = await planner(sources).research(request("DEEP"))
    assert pack.plan.mode == "DEEP" and pack.plan.max_fetches == 48
    assert ids(pack.evidence) == [W1.id, P1.id, "crossref:10.2000/ref.1"]
    reference = pack.evidence[2]
    assert (reference.followed_from, reference.facet_indexes, reference.found_by) == (
        W1.id,
        (0,),
        ("crossref",),
    )
    opened, page, followed = pack.documents
    assert (opened.content, opened.text, opened.item.licence) == (
        "FULL_TEXT",
        f"W1 abstract.\n\n{full_text}",
        "CC BY 4.0",
    )
    assert (opened.item.external_ids["open_access_url"], opened.item.doi) == (OPEN_COPY, "10.1000/a")
    assert (page.item.id, followed.content) == (P1.id, "ABSTRACT")
    assert openalex.fetched == [W1.id] and locator.asked == ["10.1000/a", "10.2000/ref.1"]
    assert crossref.fetched == ["crossref:10.2000/ref.1", "crossref:10.2000/REF.2"]
    assert [(f.stage, f.target, f.kind) for f in pack.failures] == [("FOLLOW", "10.2000/REF.2", "not_found")]


@pytest.mark.parametrize(
    ("version", "label"),
    [
        ("acceptedVersion", "author's accepted manuscript"),
        ("submittedVersion", "submitted manuscript, before peer review"),
    ],
)
async def test_a_manuscript_copy_is_cited_as_the_copy_read_and_never_as_the_published_paper(
    version: str, label: str
) -> None:
    openalex = FakeAdapter("openalex", "T3", [W1], texts={W1.id: "W1 abstract."})
    locator = FakeLocator({"10.1000/a": OPEN_COPY}, version=version)
    fetcher = FakeFetcher({OPEN_COPY: "Alum binds alizarin in the manuscript."})
    sources = LiveSources(searchers=(openalex,), fetcher=fetcher, locator=locator)
    reader = DocumentReader(sources, mode="DEEP", log=FailureLog())
    entry = PackedEvidence(item=W1, facet_indexes=(0,), found_by=("openalex",), hits=1, best_rank=1)
    (document,) = await reader.read_best([entry], limit=1)
    assert document.text == "Alum binds alizarin in the manuscript."
    item = document.item
    assert (item.id, item.title, item.url, item.doi) == (W1.id, f"Work W1 ({label})", OPEN_COPY, None)
    assert (item.external_ids["doi"], item.external_ids["open_access_version"]) == ("10.1000/a", version)
    assert item.source_key != W1.source_key


async def test_a_degraded_router_turns_deep_into_hybrid() -> None:
    openalex, crossref, web = hybrid_sources()
    pack = await planner(LiveSources(searchers=(openalex, crossref, web)), degraded=True).research(
        request("DEEP")
    )
    assert pack.degraded is True
    assert (pack.plan.mode, pack.plan.max_fetches) == ("HYBRID", 10)
    assert openalex.searched == [("Ajrakh alum mordant", 5)]


async def test_web_search_fallback_seam_reads_through_the_adapter_that_found_the_page() -> None:
    brave_only = web_page("brave-only", adapter="brave")
    searxng = FakeAdapter("searxng", "T4", [P1], texts={})
    brave = FakeAdapter(
        "brave", "T4", [web_page("p1", adapter="brave"), brave_only], texts={brave_only.id: "B"}
    )
    only_web = {
        "intent": "PROCESS",
        "needsRegion": False,
        "facets": [{"type": "PROCESS_STAGE", "target": "resist printing"}],
        "queries": [{"facetIndex": 0, "tier": "T4", "text": "Ajrakh resist printing"}],
    }
    pack = await planner(LiveSources(searchers=(WebSearch(searxng, brave),)), plan=only_web).research(
        request()
    )
    assert ids(pack.evidence) == [P1.id, brave_only.id]
    assert {entry.found_by for entry in pack.evidence} == {("web",)}
    assert [document.item.id for document in pack.documents] == [brave_only.id]
    assert searxng.fetched == [P1.id] and brave.fetched == [brave_only.id]


def test_cited_dois_are_found_once_in_text_order() -> None:
    text = (
        "See 10.1000/X1, (doi:10.1000/x1) and https://doi.org/10.5555/abc-1.; not 210.1000/no or 10.12/short."
    )
    assert dois_in(text) == ["10.1000/X1", "10.5555/abc-1"]


async def test_research_reports_each_step_with_its_count() -> None:
    steps: list[tuple[str, int]] = []

    async def progress(step: str, count: int) -> None:
        steps.append((step, count))

    openalex, crossref, web = hybrid_sources()
    await planner(LiveSources(searchers=(openalex, crossref, web))).research(request(), progress=progress)
    assert steps == [("SEARCHING_STORED", 2), ("RESEARCHING", 2), ("READING", 5)]


async def test_covered_questions_report_only_the_stored_search() -> None:
    steps: list[tuple[str, int]] = []

    async def progress(step: str, count: int) -> None:
        steps.append((step, count))

    retriever = FakeRetriever(
        {"alum": [claim("alum one"), claim("alum two")], "mordant binding": [claim("b one"), claim("b two")]}
    )
    sources = LiveSources(searchers=hybrid_sources())
    await planner(sources, retriever=retriever).research(request(), progress=progress)
    assert steps == [("SEARCHING_STORED", 2)]
