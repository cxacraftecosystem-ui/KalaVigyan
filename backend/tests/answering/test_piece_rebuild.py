import dataclasses
from decimal import Decimal

from app.core.errors import ExternalFailure
from app.providers.router import RouterError
from app.services.answer_lede import LedeTools
from app.services.piece_rebuild import StaleGroup, rebuild_group, run_piece_rebuild

from ..composer.fixtures import QUESTION
from ..research.fixtures import AJRAKH
from .fakes import SOURCES, SPENT, VIEWS, FakeResearch, FakeStore, pipeline
from .piece_fakes import MemoryPieces
from .test_answer_flow import REPLY

BUDGET = Decimal("2.50")


def group(facet: str = "CHEMISTRY", depth: str = "EXPERT") -> StaleGroup:
    return StaleGroup(
        craft=AJRAKH,
        facet=facet,
        depth=depth,
        question=QUESTION,
        asks=3,
        seats=("CHEMIST",),
        withheld_terms=("Meera Rao",),
    )


def left(*amounts: str):
    queue = [Decimal(amount) for amount in amounts]

    async def remaining() -> Decimal:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return remaining


async def test_a_stale_group_is_researched_afresh_for_its_facet_and_depth() -> None:
    pieces = MemoryPieces(views=list(VIEWS), sources=dict(SOURCES))
    research = FakeResearch()
    store = FakeStore()
    status = await rebuild_group(
        group(), pipeline(research=research, replies=[REPLY], store=store, pieces=pieces)
    )
    assert status == "REBUILT"
    (request,) = research.requests
    assert (request.focus, request.depth, request.mode) == ("CHEMISTRY", "EXPERT", "DEEP")
    assert (request.withheld_terms, request.seats) == (("Meera Rao",), ("CHEMIST",))
    ((ask, understanding),) = store.begun
    assert (ask.fresh, ask.craft_slug, ask.user_id) == (True, AJRAKH.slug, None)
    assert (understanding.disciplines, understanding.craft) == (["CHEMISTRY"], AJRAKH)
    assert pieces.asked[-1].fresh is True
    (kept,) = pieces.current()
    assert (kept.facet, kept.depth) == ("CHEMISTRY", "EXPERT")


async def test_a_rebuild_has_no_reader_so_it_writes_no_lede() -> None:
    asked: list[object] = []

    async def lede(request: object) -> object:
        asked.append(request)
        raise AssertionError("a rebuild writes no lede")

    pieces = MemoryPieces(views=list(VIEWS), sources=dict(SOURCES))
    built = dataclasses.replace(pipeline(replies=[REPLY], pieces=pieces), lede=LedeTools(compose=lede))
    assert await rebuild_group(group(), built) == "REBUILT"
    assert asked == []


async def test_a_rebuild_that_shows_nothing_is_reported_empty() -> None:
    status = await rebuild_group(group(), pipeline(replies=['{"sentences": [], "followUps": []}'] * 2))
    assert status == "EMPTY"


async def test_the_rebuild_stops_when_the_day_budget_is_spent() -> None:
    done: list[StaleGroup] = []

    async def rebuild(stale: StaleGroup) -> str:
        done.append(stale)
        return "REBUILT"

    report = await run_piece_rebuild(
        [group(), group("HISTORY")], rebuild=rebuild, remaining=left("1.00", "0.10"), budget_usd=BUDGET
    )
    assert [stale.facet for stale in done] == ["CHEMISTRY"]
    assert (report.stopped, [g.status for g in report.groups], report.ok) == ("BUDGET", ["REBUILT"], True)


async def test_a_spend_refusal_stops_the_run_and_other_failures_are_reported() -> None:
    async def rebuild(stale: StaleGroup) -> str:
        if stale.facet == "HISTORY":
            raise ExternalFailure("research failed", kind="unavailable", service="live_research")
        raise RouterError("ceiling", SPENT, reason="MONTHLY_CEILING")

    report = await run_piece_rebuild(
        [group("HISTORY"), group(), group("DESIGN")],
        rebuild=rebuild,
        remaining=left("2.00"),
        budget_usd=BUDGET,
    )
    assert [(g.facet, g.status, g.error) for g in report.groups] == [
        ("HISTORY", "FAILED", "research failed"),
        ("CHEMISTRY", "FAILED", SPENT),
    ]
    assert (report.stopped, report.ok) == ("SPEND_REFUSED", False)
    assert report.as_dict()["budget_usd"] == "2.50"


async def test_a_group_whose_rebuild_ran_is_marked_tried_and_a_failed_one_is_not() -> None:
    marked: list[str] = []

    async def rebuild(stale: StaleGroup) -> str:
        if stale.facet == "HISTORY":
            raise ExternalFailure("research failed", kind="unavailable", service="live_research")
        return "EMPTY" if stale.facet == "DESIGN" else "REBUILT"

    async def tried(stale: StaleGroup) -> None:
        marked.append(stale.facet)

    report = await run_piece_rebuild(
        [group(), group("HISTORY"), group("DESIGN")],
        rebuild=rebuild,
        remaining=left("2.00"),
        budget_usd=BUDGET,
        tried=tried,
    )
    assert [g.status for g in report.groups] == ["REBUILT", "FAILED", "EMPTY"]
    assert marked == ["CHEMISTRY", "DESIGN"]
