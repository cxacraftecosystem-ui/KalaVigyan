from typing import Any

import pytest

from app.planner import orchestrator
from app.planner.drafting import draft_plan
from app.planner.policy import reference_reserve, seat_reading_kinds
from app.planner.reading import LiveSources, reading_order
from app.research.evidence_pack import PackedEvidence
from app.research.expert_panel import EXPERT_PANEL
from app.research.planning import ResearchShare

from ..research.fixtures import evidence_item
from .fakes import FakeAdapter, FakeFetcher, FakeLocator, ids, model_for, request, web_page
from .test_research_run import OPEN_COPY, P1, W1, planner

HISTORIAN_READS = (
    "BOOK",
    "PAPER",
    "GI_JOURNAL",
    "ENCYCLOPEDIA",
    "BOOK_CHAPTER",
    "WEB_PAGE",
    "MEDIA",
    "OTHER",
)
TOXICOLOGIST_READS = ("COMPOUND_RECORD", "PAPER", "GOVERNMENT_REPORT", "BOOK_CHAPTER")
CHEMIST_READS = ("PAPER", "BOOK", "COMPOUND_RECORD", "ENCYCLOPEDIA", "BOOK_CHAPTER", "GI_JOURNAL", "WEB_PAGE")


def packed(native: str, kind: str, facet: int) -> PackedEvidence:
    item = evidence_item(
        id=f"openalex:{native}", sourceType=kind, doi=None, url=f"https://works.example.org/{native}"
    )
    return PackedEvidence(item=item, facet_indexes=(facet,), found_by=("openalex",), hits=1, best_rank=1)


PAPER_ONE = packed("paper-1", "PAPER", 0)
PAPER_TWO = packed("paper-2", "PAPER", 0)
PAGE = packed("page", "WEB_PAGE", 1)
ARTICLE = packed("article", "ENCYCLOPEDIA", 0)
RECORD = packed("record", "COMPOUND_RECORD", 1)
RANKED = [PAPER_ONE, PAPER_TWO, PAGE, ARTICLE, RECORD]


def test_without_experts_each_facet_reads_its_best_item_first() -> None:
    assert ids(reading_order(RANKED, 2)) == ids([PAPER_ONE, PAGE, PAPER_TWO, ARTICLE, RECORD])


def test_each_expert_s_preferred_kind_takes_every_other_early_read() -> None:
    ordered = reading_order(RANKED, 2, (HISTORIAN_READS, TOXICOLOGIST_READS))
    assert ids(ordered) == ids([PAPER_ONE, PAPER_TWO, PAGE, RECORD, ARTICLE])


def test_an_expert_reads_its_most_preferred_kind_found_not_the_best_ranked() -> None:
    ordered = reading_order(RANKED, 1, (("ENCYCLOPEDIA", "PAPER"),))
    assert ids(ordered)[:2] == ids([PAPER_ONE, ARTICLE])


def test_an_expert_with_no_kind_found_takes_no_read() -> None:
    ordered = reading_order(RANKED, 2, (("GI_JOURNAL",),))
    assert ids(ordered) == ids(reading_order(RANKED, 2))


def test_the_section_s_speaking_seats_give_their_kinds_in_seat_order() -> None:
    seated = ("CHEMIST", "HISTORIAN", "ARTISAN", "TOXICOLOGIST")
    assert seat_reading_kinds(request(focus="HISTORY", seats=seated, depth="DETAILED")) == (HISTORIAN_READS,)
    assert seat_reading_kinds(request(focus="HISTORY", seats=seated, depth="EXPERT")) == (
        HISTORIAN_READS,
        *(
            EXPERT_PANEL[seat].source_kinds
            for seat in ("ANTHROPOLOGIST", "DESIGN_HISTORIAN", "POLICY_EXPERT")
        ),
    )
    assert seat_reading_kinds(request(focus="HEALTH", seats=seated, depth="EXPERT")) == (
        CHEMIST_READS,
        TOXICOLOGIST_READS,
        EXPERT_PANEL["ECOLOGIST"].source_kinds,
    )
    assert seat_reading_kinds(request(focus="HEALTH", seats=seated, depth="BASIC")) == (CHEMIST_READS,)
    assert seat_reading_kinds(request(seats=seated, depth="EXPERT")) == ()


async def test_a_section_plan_names_no_artisan_and_the_kinds_each_expert_reads() -> None:
    model = model_for()
    await draft_plan(model, request(focus="PROCESS", seats=("ARTISAN", "TECHNOLOGIST"), depth="DETAILED"))
    (call,) = model.calls
    reads = "paper, government report, gi journal, book, book chapter, web page, other"
    assert f"Experts: textile or ceramic technologist, reading {reads}\n" in call["user"]
    assert "artisan" not in call["user"].casefold()


async def test_the_planner_hands_the_reading_order_the_section_s_experts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    heard: list[Any] = []

    def recorded(evidence: Any, facet_count: int, seat_kinds: Any = ()) -> list[PackedEvidence]:
        heard.append(seat_kinds)
        return reading_order(evidence, facet_count, seat_kinds)

    monkeypatch.setattr(orchestrator, "reading_order", recorded)
    openalex = FakeAdapter("openalex", "T3", [W1], texts={W1.id: "W1 abstract."})
    web = FakeAdapter("web", "T4", [web_page("p1")], texts={})
    sections = request(focus="HISTORY", seats=("HISTORIAN", "CHEMIST"), depth="DETAILED")
    await planner(LiveSources(searchers=(openalex, web))).research(sections)
    assert heard == [(HISTORIAN_READS,)]


@pytest.mark.parametrize(("fetches", "reserved"), [(20, 6), (10, 3), (4, 1), (3, 0), (0, 0)])
def test_deep_keeps_for_references_the_same_part_of_any_share(fetches: int, reserved: int) -> None:
    assert reference_reserve(fetches) == reserved


async def test_a_deep_section_with_a_small_share_still_reads_what_it_found() -> None:
    openalex = FakeAdapter("openalex", "T3", [W1], texts={W1.id: "W1 abstract."})
    web = FakeAdapter("web", "T4", [P1], texts={P1.id: "As in 10.1000/a, see the page."})
    crossref = FakeAdapter("crossref", "T3", texts={"crossref:10.2000/ref.1": "Ref 1 abstract."})
    full_text = "Alum binds alizarin (doi:10.2000/ref.1; https://doi.org/10.2000/REF.2.) as 10.1000/a showed."
    sources = LiveSources(
        searchers=(openalex, web),
        fetcher=FakeFetcher({OPEN_COPY: full_text}),
        locator=FakeLocator({"10.1000/a": OPEN_COPY}),
        doi_source=crossref,
    )
    share = ResearchShare(queries=2, native_queries=0, fetches=4)
    pack = await planner(sources).research(request("DEEP", share=share))
    assert pack.plan.max_fetches == 4
    assert [document.item.id for document in pack.documents] == [W1.id, P1.id, "crossref:10.2000/ref.1"]
