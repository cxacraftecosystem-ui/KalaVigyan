import asyncio
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Any

import pytest

from app.planner.policy import SEAT_LIVE_SHARE, SEAT_RESEARCH_DEPTHS, SEAT_SENTENCES_MAX, seat_gap_field
from app.research.composition import ComposedAnswer, ComposeRequest
from app.research.coverage import CoverageSubject, Holdings, field_coverage
from app.research.evidence_pack import EvidencePack
from app.research.expert_panel import EXPERT_PANEL
from app.research.planning import PlanRequest, ResearchShare
from app.services import seat_search
from app.services.answer_events import CitedClaims, cited_claims
from app.services.research_ledger import ResearchLedger
from app.services.seat_research import GapResearch, seat_request
from app.services.seat_search import live_findings, seat_gaps, with_live

from ..answering.fakes import stored_view
from ..composer.fixtures import pack
from .fixtures import QUESTION, build_ask, claim, source

CHEMIST = EXPERT_PANEL["CHEMIST"]
HISTORIAN = EXPERT_PANEL["HISTORIAN"]
WEB = source(9, "WEB_PAGE", "Alum in Kutch", "https://example.org/alum")
FOUND = stored_view(
    claim(30),
    "Alum fixes the red of madder to the cotton in Ajrakh printing.",
    "PROVISIONAL",
    (130, WEB, "Alum fixes the red of madder to the cotton", "para. 3"),
)
OLDER = stored_view(
    claim(31),
    "The printers boil the cloth with alum before the madder bath.",
    "PROVISIONAL",
    (131, WEB, "boil the cloth with alum before the madder bath", "para. 4"),
)


def coverage(**filed: tuple[str, ...]) -> Any:
    holdings = Holdings(
        filed={claim_id: frozenset(fields) for claim_id, fields in filed.items()},
        sources={claim_id: frozenset({"s"}) for claim_id in filed},
    )
    return field_coverage(CoverageSubject("craft", "Kutch-Ajrakh", "Kutch Ajrakh"), holdings, claims_min=3)


def test_a_seat_researches_live_only_while_its_own_field_is_missing_or_thin() -> None:
    covered = coverage(a=("CHEMISTRY",), b=("CHEMISTRY",), c=("CHEMISTRY",))
    thin = coverage(a=("CHEMISTRY",))
    assert CHEMIST.fields[0] == "CHEMISTRY"
    assert seat_gap_field(CHEMIST, covered) is None
    assert seat_gap_field(CHEMIST, thin) == "CHEMISTRY"
    assert seat_gap_field(CHEMIST, coverage()) == "CHEMISTRY"
    assert seat_gap_field(CHEMIST, None) is None
    assert (SEAT_LIVE_SHARE.queries, SEAT_LIVE_SHARE.native_queries, SEAT_LIVE_SHARE.fetches) == (1, 0, 1)


@dataclass
class FakeTools:
    found: EvidencePack = field(default_factory=pack)
    failure: Exception | None = None
    requests: list[PlanRequest] = field(default_factory=list)
    composed: list[ComposeRequest] = field(default_factory=list)
    kept: list[EvidencePack] = field(default_factory=list)

    async def research(self, request: PlanRequest, progress: Any, trail: Any) -> EvidencePack:
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        return self.found

    async def compose(self, request: ComposeRequest) -> ComposedAnswer:
        self.composed.append(request)
        return ComposedAnswer.model_construct()

    async def keep(self, answer_id: uuid.UUID, found: EvidencePack, composed: ComposedAnswer) -> Any:
        self.kept.append(found)
        return ((FOUND.id,),)

    async def cited(self, claim_ids: Iterable[uuid.UUID]) -> CitedClaims:
        wanted = set(claim_ids)
        return cited_claims([view for view in (FOUND,) if view.id in wanted], {WEB.id: WEB})


def researcher(tools: FakeTools, budget: ResearchShare) -> tuple[GapResearch, ResearchLedger]:
    ledger = ResearchLedger(budget, 1)
    base = build_ask(("CHEMIST",), discipline="CHEMISTRY", depth="EXPERT").request
    gap = GapResearch(uuid.uuid4(), base, ledger, tools.research, tools.compose, tools, trail=None)  # type: ignore[arg-type]
    return gap, ledger


async def test_a_gap_seat_reads_one_source_and_writes_its_findings_back() -> None:
    tools = FakeTools()
    gap, ledger = researcher(tools, ResearchShare(queries=2, native_queries=0, fetches=2))
    found = await gap(CHEMIST, "CHEMISTRY")
    assert list(found.views) == [FOUND.id]
    (asked,) = tools.requests
    assert (asked.focus, asked.fresh, asked.seats, asked.question) == (
        "CHEMISTRY",
        True,
        ("CHEMIST",),
        QUESTION,
    )
    assert asked.share == ResearchShare(queries=1, native_queries=0, fetches=1)
    (compose,) = tools.composed
    assert compose.focus is not None and compose.focus.sentences_max == SEAT_SENTENCES_MAX
    assert tools.kept == [tools.found]
    assert ledger.left == ResearchShare(queries=1, native_queries=0, fetches=1)


async def test_a_spent_budget_keeps_the_seat_on_stored_evidence() -> None:
    tools = FakeTools()
    gap, ledger = researcher(tools, ResearchShare(queries=1, native_queries=0, fetches=0))
    assert await gap(CHEMIST, "CHEMISTRY") == CitedClaims()
    assert tools.requests == [] and ledger.left == ResearchShare(queries=1, native_queries=0, fetches=0)


async def test_a_failed_search_gives_the_budget_back_and_a_bare_one_writes_nothing() -> None:
    failing = FakeTools(failure=RuntimeError("search down"))
    gap, ledger = researcher(failing, ResearchShare(queries=2, native_queries=0, fetches=2))
    with pytest.raises(RuntimeError):
        await gap(CHEMIST, "CHEMISTRY")
    assert ledger.left == ResearchShare(queries=2, native_queries=0, fetches=2)
    bare = FakeTools(found=pack(documents=()))
    gap, _ = researcher(bare, ResearchShare(queries=2, native_queries=0, fetches=2))
    assert await gap(CHEMIST, "CHEMISTRY") == CitedClaims()
    assert bare.composed == [] and bare.kept == []


def test_a_seat_s_request_keeps_the_question_and_names_its_seat_and_share() -> None:
    base = build_ask(("HISTORIAN",)).request
    asked = seat_request(base, HISTORIAN, "HISTORY", SEAT_LIVE_SHARE)
    assert (asked.question, asked.craft, asked.focus) == (base.question, base.craft, "HISTORY")
    assert (asked.seats, asked.share, asked.fresh) == (("HISTORIAN",), SEAT_LIVE_SHARE, True)


async def test_live_findings_lead_the_seat_s_evidence_and_a_failure_keeps_it_stored() -> None:
    async def research(brief: Any, discipline: str) -> CitedClaims:
        if brief.seat == "HISTORIAN":
            raise TimeoutError
        return cited_claims([FOUND], {WEB.id: WEB})

    ask = replace(build_ask(("CHEMIST", "HISTORIAN")), research=research)
    live = await live_findings(ask, {"CHEMIST": (CHEMIST, "CHEMISTRY"), "HISTORIAN": (HISTORIAN, "HISTORY")})
    assert list(live) == ["CHEMIST"]
    merged = with_live({"CHEMIST": (OLDER, FOUND), "HISTORIAN": (OLDER,)}, live, shown=set())
    assert merged == {"CHEMIST": (FOUND, OLDER), "HISTORIAN": (OLDER,)}
    assert with_live({}, live, shown={str(FOUND.id)}) == {"CHEMIST": ()}
    assert await live_findings(build_ask(("CHEMIST",)), {"CHEMIST": (CHEMIST, "CHEMISTRY")}) == {}


async def test_a_cancelled_live_search_is_not_swallowed() -> None:
    async def research(brief: Any, discipline: str) -> CitedClaims:
        raise asyncio.CancelledError

    ask = replace(build_ask(("CHEMIST",)), research=research)
    with pytest.raises(asyncio.CancelledError):
        await live_findings(ask, {"CHEMIST": (CHEMIST, "CHEMISTRY")})


class OpenedSessions:
    def __call__(self) -> OpenedSessions:
        return self

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *raised: object) -> None:
        return None


async def test_only_an_expert_answer_s_seats_with_a_gap_research(monkeypatch: pytest.MonkeyPatch) -> None:
    async def craft_coverage(session: Any, slug: str) -> Any:
        return coverage(a=("HISTORY",), b=("HISTORY",), c=("HISTORY",))

    async def research(brief: Any, discipline: str) -> CitedClaims:
        return CitedClaims()

    monkeypatch.setattr(seat_search, "craft_coverage", craft_coverage)
    expert = replace(build_ask(("CHEMIST", "HISTORIAN"), depth="EXPERT"), research=research)
    gaps = await seat_gaps(OpenedSessions(), expert, (CHEMIST, HISTORIAN))  # type: ignore[arg-type]
    assert gaps == {"CHEMIST": (CHEMIST, "CHEMISTRY")}
    detailed = replace(build_ask(("CHEMIST",), depth="DETAILED"), research=research)
    assert await seat_gaps(None, detailed, (CHEMIST,)) == {}  # type: ignore[arg-type]
    assert await seat_gaps(None, build_ask(("CHEMIST",), depth="EXPERT"), (CHEMIST,)) == {}  # type: ignore[arg-type]
    assert frozenset({"EXPERT"}) == SEAT_RESEARCH_DEPTHS
