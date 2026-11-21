from app.planner.drafting import draft_plan
from app.planner.reading import LiveSources
from app.research.evidence import SourceDocument
from app.research.evidence_pack import PackedEvidence
from app.research.planning import ResearchShare

from .fakes import FakeRetriever, claim, model_for, request
from .test_research_run import hybrid_sources, planner

COVERED = {
    "alum": [claim("alum one"), claim("alum two")],
    "mordant binding": [claim("b one"), claim("b two")],
}


class Trail:
    def __init__(self) -> None:
        self.found_ids: list[str] = []
        self.read_ids: list[str] = []

    async def found(self, evidence: list[PackedEvidence]) -> None:
        self.found_ids += [entry.item.id for entry in evidence]

    async def read(self, document: SourceDocument) -> None:
        self.read_ids.append(document.item.id)


async def test_a_section_plan_names_its_field_and_the_experts_who_speak_to_it() -> None:
    model = model_for()
    share = ResearchShare(queries=1, native_queries=0, fetches=3)
    await draft_plan(model, request(focus="CHEMISTRY", seats=("CHEMIST", "DESIGN_HISTORIAN"), share=share))
    (call,) = model.calls
    experts = "Experts: chemist, reading paper, book, compound record, encyclopedia, book chapter, gi journal, web page"
    assert f"Section: chemistry\n{experts}\n" in call["user"]
    assert "Queries: at most 1\n" in call["user"]


async def test_a_section_researches_within_its_share() -> None:
    openalex, crossref, web = hybrid_sources()
    share = ResearchShare(queries=1, native_queries=0, fetches=1)
    pack = await planner(LiveSources(searchers=(openalex, crossref, web))).research(request(share=share))
    assert [query.query.text for query in pack.plan.queries] == ["Ajrakh alum mordant"]
    assert (pack.plan.max_fetches, len(pack.documents)) == (1, 1)


async def test_fresh_research_searches_live_even_where_stored_claims_cover_the_facet() -> None:
    sources = LiveSources(searchers=hybrid_sources())
    stored_first = await planner(sources, retriever=FakeRetriever(COVERED)).research(request())
    fresh = await planner(sources, retriever=FakeRetriever(COVERED)).research(request(fresh=True))
    assert stored_first.plan.queries == []
    assert [query.facet_index for query in fresh.plan.queries] == [0, 1]


async def test_the_trail_hears_each_source_found_and_each_document_read() -> None:
    trail = Trail()
    openalex, crossref, web = hybrid_sources()
    pack = await planner(LiveSources(searchers=(openalex, crossref, web))).research(request(), trail=trail)
    assert trail.found_ids == [entry.item.id for entry in pack.evidence]
    assert sorted(trail.read_ids) == sorted(document.item.id for document in pack.documents)
