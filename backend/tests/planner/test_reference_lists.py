from dataclasses import dataclass, field

from app.core.errors import ExternalFailure
from app.planner.orchestrator import ResearchPlanner
from app.planner.reading import LiveSources
from app.planner.references import CitedDoi, CitedList, cited_lists
from app.research.evidence import EvidenceItem, SourceDocument
from app.research.evidence_pack import PackedEvidence
from app.sources.adapter import build_document

from .fakes import FakeAdapter, FakeRetriever, ids, model_for, request, scholarly, web_page

W1 = scholarly("W1", doi="10.1000/a")
W2 = scholarly("W2", doi="10.1000/b")
P1 = web_page("p1")
LISTED = [scholarly(f"R{n}", doi=f"10.3000/r.{n}") for n in range(1, 7)]
W1_TEXT = "W1 abstract citing 10.2000/a.1 and 10.2000/a.2."


@dataclass
class FakeLister:
    lists_of: dict[str, list[EvidenceItem]]
    failure: ExternalFailure | None = None
    name: str = "openalex"
    asked: list[tuple[str, int]] = field(default_factory=list)

    def lists(self, item: EvidenceItem) -> bool:
        return item.id in self.lists_of

    async def references(self, item: EvidenceItem, k: int) -> list[SourceDocument]:
        self.asked.append((item.id, k))
        if self.failure is not None:
            raise self.failure
        return [
            build_document(listed, f"{listed.title} abstract.", "ABSTRACT")
            for listed in self.lists_of[item.id]
        ][:k]


def deep_sources(lister: FakeLister) -> LiveSources:
    openalex = FakeAdapter("openalex", "T3", [W1], texts={W1.id: W1_TEXT})
    web = FakeAdapter("web", "T4", [P1], texts={P1.id: "P1 page text on mordants."})
    texts = {"crossref:10.2000/a.1": "A1 abstract.", "crossref:10.2000/a.2": "A2 abstract."}
    crossref = FakeAdapter("crossref", "T3", texts=texts)
    return LiveSources(searchers=(openalex, web), doi_source=crossref, reference_source=lister)


def planner(sources: LiveSources) -> ResearchPlanner:
    return ResearchPlanner(model=model_for(), retriever=FakeRetriever(), sources=sources)


def packed(item: EvidenceItem) -> PackedEvidence:
    return PackedEvidence(item=item, facet_indexes=(0,), found_by=(item.adapter,), hits=1, best_rank=1)


def read(item: EvidenceItem) -> SourceDocument:
    return build_document(item, f"{item.title} text.", "ABSTRACT")


async def test_deep_research_follows_a_reference_list_in_the_room_its_cited_dois_leave() -> None:
    lister = FakeLister({W1.id: LISTED})
    pack = await planner(deep_sources(lister)).research(request("DEEP"))
    assert lister.asked == [(W1.id, 3)]
    followed = ["crossref:10.2000/a.1", "crossref:10.2000/a.2", *(item.id for item in LISTED[:3])]
    assert ids(pack.evidence) == [W1.id, P1.id, *followed]
    listed = pack.evidence[4:]
    assert [(entry.found_by, entry.followed_from, entry.best_rank) for entry in listed] == [
        (("openalex",), W1.id, 3),
        (("openalex",), W1.id, 4),
        (("openalex",), W1.id, 5),
    ]
    assert [document.item.id for document in pack.documents][2:] == followed


async def test_a_reference_list_that_fails_is_recorded_and_the_dois_still_followed() -> None:
    down = ExternalFailure("openalex is down", kind="unavailable", service="openalex")
    pack = await planner(deep_sources(FakeLister({W1.id: LISTED}, failure=down))).research(request("DEEP"))
    assert ids(pack.evidence) == [W1.id, P1.id, "crossref:10.2000/a.1", "crossref:10.2000/a.2"]
    assert [(f.stage, f.service, f.target, f.kind) for f in pack.failures] == [
        ("FOLLOW", "openalex", W1.id, "unavailable")
    ]


async def test_measured_hybrid_answers_follow_no_reference_list() -> None:
    lister = FakeLister({W1.id: LISTED})
    pack = await planner(deep_sources(lister)).research(request())
    assert lister.asked == [] and ids(pack.evidence) == [W1.id, P1.id]


def test_lists_share_the_room_left_and_each_document_keeps_five_references() -> None:
    first, second = packed(W1), packed(W2)
    documents = [read(W1), read(W2)]
    assert cited_lists([first, second], documents, [], limit=4) == [CitedList(first, 1, 4)]
    cited = [CitedDoi("10.2000/a.1", first, 1), CitedDoi("10.2000/a.2", first, 2)]
    assert cited_lists([first, second], documents, cited, limit=9) == [
        CitedList(first, 3, 3),
        CitedList(second, 1, 4),
    ]
