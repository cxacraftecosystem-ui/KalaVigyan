from typing import Any

import pytest
from pydantic import ValidationError

from app.core.errors import ExternalFailure
from app.planner.orchestrator import ResearchPlanner
from app.planner.reading import LiveSources
from app.research.evidence_pack import EvidencePack

from .fakes import FakeAdapter, FakeRetriever, claim, model_for, request, scholarly, web_page

TWO_T3_QUERIES: dict[str, Any] = {
    "intent": "SCIENCE",
    "needsRegion": False,
    "facets": [
        {"type": "MATERIAL", "target": "alum"},
        {"type": "MECHANISM", "target": "mordant binding"},
    ],
    "queries": [
        {"facetIndex": 0, "tier": "T3", "text": "Ajrakh alum mordant"},
        {"facetIndex": 1, "tier": "T3", "text": "Ajrakh alizarin alum lake chemistry"},
    ],
}
W1 = scholarly("W1", doi=None)


def searchers() -> tuple[FakeAdapter, FakeAdapter, FakeAdapter]:
    openalex = FakeAdapter("openalex", "T3", [W1], texts={W1.id: "W1 abstract on alum."})
    web = FakeAdapter("web", "T4", [web_page("p1")])
    crossref = FakeAdapter("crossref", "T3")
    return openalex, web, crossref


async def researched(
    adapters: tuple[FakeAdapter, ...], retriever: FakeRetriever | None = None
) -> EvidencePack:
    sources = LiveSources(searchers=adapters)
    model = model_for(TWO_T3_QUERIES)
    planner = ResearchPlanner(model=model, retriever=retriever or FakeRetriever(), sources=sources)
    return await planner.research(request())


async def test_a_pack_names_each_searcher_its_queries_asked_once_found_evidence_or_not() -> None:
    openalex, web, crossref = searchers()
    pack = await researched((openalex, web, crossref))
    assert (len(openalex.searched), len(crossref.searched), web.searched) == (2, 2, [])
    assert {name for entry in pack.evidence for name in entry.found_by} == {"openalex"}
    assert pack.searched == ("openalex", "crossref")
    assert EvidencePack.model_validate(pack.model_dump()) == pack


async def test_a_pack_answered_from_stored_knowledge_names_no_searcher() -> None:
    covered = {
        "alum": [claim("alum one"), claim("alum two")],
        "mordant binding": [claim("b one"), claim("b two")],
    }
    pack = await researched(searchers(), FakeRetriever(covered))
    assert pack.plan.queries == []
    assert pack.searched == ()


async def test_a_searcher_whose_searches_failed_is_still_named() -> None:
    openalex, web, crossref = searchers()
    crossref.search_failure = ExternalFailure("crossref is down", kind="unavailable", service="crossref")
    pack = await researched((openalex, web, crossref))
    assert [f.service for f in pack.failures if f.stage == "SEARCH"] == ["crossref", "crossref"]
    assert pack.searched == ("openalex", "crossref")


async def test_a_pack_stored_before_searchers_were_recorded_still_reads_and_names_none() -> None:
    stored = (await researched(searchers())).model_dump()
    del stored["searched"]
    assert EvidencePack.model_validate(stored).searched == ()


async def test_a_pack_naming_a_searcher_twice_is_refused() -> None:
    stored = (await researched(searchers())).model_dump()
    with pytest.raises(ValidationError, match="searched names each live searcher once"):
        EvidencePack.model_validate(stored | {"searched": ["openalex", "openalex"]})
