import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.composer.candidates import research_summary
from app.core.errors import ExternalFailure, NotConfigured
from app.core.logging import current_request_id, request_id_scope
from app.models import EnrichmentJob
from app.providers.router import RouterError
from app.research.composition import ComposedAnswer
from app.research.evidence_pack import EvidencePack
from app.research.planning import PlanRequest
from app.retrieval.indexing import EmbeddedCounts
from app.services import coverage_enrichment
from app.services.coverage_enrichment import EnrichmentPipeline, run_coverage_enrichment
from app.services.coverage_selection import STANDARD_QUESTIONS, CraftToEnrich, open_questions
from app.services.craft_resolver import CraftIndexStore
from app.services.research_write_back import StoredResearch
from app.services.write_back_plan import SkippedSentence

from ..composer.fixtures import pack
from ..craft_fixtures import FixedEmbedder

DAY = datetime(2026, 11, 15, 18, 30, tzinfo=UTC)
FIRST = CraftToEnrich(uuid.UUID(int=1), "Kutch-Ajrakh", "Kutch Ajrakh", 0)
SECOND = CraftToEnrich(uuid.UUID(int=2), "Bagru-Print", "Bagru Print", 3, {"PROCESS": 2})


class FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.statements: list[Any] = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def execute(self, statement: Any) -> None:
        self.statements.append(statement)

    def finished(self) -> list[dict[str, Any]]:
        found = []
        for statement in self.statements:
            values = {column.key: value.value for column, value in statement._values.items()}
            found.append(values)
        return found


@dataclass
class FakePipeline:
    cost_per_question: Decimal = Decimal("0.20")
    failures: dict[str, Exception] = field(default_factory=dict)
    with_documents: bool = True
    asked: list[tuple[str, str, str | None]] = field(default_factory=list)
    composed: int = 0
    spend: dict[str, Decimal] = field(default_factory=dict)

    async def research(self, request: PlanRequest) -> EvidencePack:
        tag = current_request_id()
        self.asked.append((request.craft.slug, request.question, tag))
        self.spend[tag] = self.spend.get(tag, Decimal(0)) + self.cost_per_question
        if request.craft.slug in self.failures:
            raise self.failures[request.craft.slug]
        return pack() if self.with_documents else pack(documents=())

    async def compose(self, evidence: EvidencePack, question: str) -> ComposedAnswer:
        self.composed += 1
        return ComposedAnswer(not_enough_evidence=research_summary(evidence))

    async def spent(self, prefix: str, since: datetime) -> Decimal:
        assert since == DAY
        return sum((amount for tag, amount in self.spend.items() if tag.startswith(prefix)), Decimal(0))

    def as_pipeline(self) -> EnrichmentPipeline:
        return EnrichmentPipeline(
            research=self.research,
            compose=self.compose,
            embed=FixedEmbedder(),
            spent=self.spent,
            index=CraftIndexStore(),
        )


@pytest.fixture
def stored(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    calls: list[tuple[str, Any]] = []

    async def fake_store(session: Any, evidence: Any, answer: Any, **options: Any) -> StoredResearch:
        calls.append((evidence.plan.craft.slug, options))
        return StoredResearch(
            source_ids=(uuid.UUID(int=7), uuid.UUID(int=8)),
            results=(),
            skipped=(SkippedSentence("s", "cites stored claims only"),),
            embedded=EmbeddedCounts(claims=0, chunks=0),
        )

    monkeypatch.setattr(coverage_enrichment, "store_live_research", fake_store)
    return calls


def crafts(monkeypatch: pytest.MonkeyPatch, *picked: CraftToEnrich) -> None:
    async def fake_pick(session: Any, *, now: datetime, limit: int) -> list[CraftToEnrich]:
        assert limit == coverage_enrichment.ENRICHMENT_CRAFTS_PER_RUN
        return list(picked)

    monkeypatch.setattr(coverage_enrichment, "least_covered_crafts", fake_pick)


def test_only_questions_whose_field_holds_fewer_than_two_claims_are_asked() -> None:
    craft = CraftToEnrich(uuid.UUID(int=3), "Kutch-Ajrakh", "Kutch Ajrakh", 3, {"PROCESS": 2, "CHEMISTRY": 1})
    assert [q.facet for q in open_questions(craft)] == [
        "MATERIAL",
        "MECHANISM",
        "TOOL",
        "ENVIRONMENTAL_CONDITION",
        "HISTORICAL_CONTEXT",
    ]
    assert [q.field for q in STANDARD_QUESTIONS] == [
        "MATERIALS",
        "PROCESS",
        "CHEMISTRY",
        "MATERIALS",
        "GEOGRAPHY",
        "HISTORY",
    ]
    assert (
        STANDARD_QUESTIONS[1].text_for("Kutch Ajrakh")
        == "What are the stages of making Kutch Ajrakh, in order?"
    )


def test_a_question_whose_last_run_added_nothing_rests_and_two_facts_in_a_field_close_both_its_questions() -> (
    None
):
    resting = CraftToEnrich(
        uuid.UUID(int=4), "Kutch-Ajrakh", "Kutch Ajrakh", 2, {"MATERIALS": 2}, frozenset({"MECHANISM"})
    )
    assert [q.facet for q in open_questions(resting)] == [
        "PROCESS_STAGE",
        "ENVIRONMENTAL_CONDITION",
        "HISTORICAL_CONTEXT",
    ]


async def test_the_run_stops_before_a_question_would_pass_the_daily_budget(
    monkeypatch: pytest.MonkeyPatch, stored: list[tuple[str, Any]]
) -> None:
    crafts(monkeypatch, FIRST, SECOND)
    fake = FakePipeline()
    session = FakeSession()
    report = await run_coverage_enrichment(
        session, fake.as_pipeline(), day_started_at=DAY, budget_usd=Decimal("0.60")
    )
    assert report.stopped == "BUDGET"
    assert [(c.slug, c.status, c.questions, c.documents) for c in report.crafts] == [
        ("Kutch-Ajrakh", "SUCCEEDED", 2, 4)
    ]
    assert report.spent_usd == "0.40"
    assert report.ok
    (job,) = session.added
    assert isinstance(job, EnrichmentJob)
    assert (job.mode, job.status, job.budgetUsd) == ("HYBRID", "RUNNING", Decimal("0.60"))
    assert job.facets == [q.facet for q in STANDARD_QUESTIONS]
    tag = f"enrichment-{job.id.hex}"
    assert {asked[2] for asked in fake.asked} == {tag}
    assert [options["found_by"] for _, options in stored] == ["BACKGROUND", "BACKGROUND"]
    (finished,) = session.finished()
    assert (finished["status"], finished["spentUsd"]) == ("SUCCEEDED", Decimal("0.40"))


async def test_a_failing_craft_is_recorded_and_the_next_craft_still_runs(
    monkeypatch: pytest.MonkeyPatch, stored: list[tuple[str, Any]]
) -> None:
    crafts(monkeypatch, FIRST, SECOND)
    fake = FakePipeline(
        failures={"Kutch-Ajrakh": ExternalFailure("openalex unavailable", kind="unavailable")}
    )
    session = FakeSession()
    report = await run_coverage_enrichment(
        session, fake.as_pipeline(), day_started_at=DAY, budget_usd=Decimal("5")
    )
    assert [(c.slug, c.status) for c in report.crafts] == [
        ("Kutch-Ajrakh", "FAILED"),
        ("Bagru-Print", "SUCCEEDED"),
    ]
    assert report.crafts[0].error == "openalex unavailable"
    assert report.crafts[1].questions == 5
    assert report.stopped is None
    assert not report.ok
    assert session.rollbacks == 1


@pytest.mark.parametrize(
    ("error", "stop"),
    [
        (RouterError("ceiling", "Budget reached"), "ceiling"),
        (NotConfigured("crossref", "crossref must be built"), "not_configured:crossref"),
    ],
)
async def test_a_spent_ceiling_or_missing_setup_stops_the_run(
    monkeypatch: pytest.MonkeyPatch, stored: list[tuple[str, Any]], error: Exception, stop: str
) -> None:
    crafts(monkeypatch, FIRST, SECOND)
    fake = FakePipeline(failures={"Kutch-Ajrakh": error})
    report = await run_coverage_enrichment(FakeSession(), fake.as_pipeline(), day_started_at=DAY)
    assert report.stopped == stop
    assert [c.slug for c in report.crafts] == ["Kutch-Ajrakh"]


async def test_a_pack_without_documents_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, stored: list[tuple[str, Any]]
) -> None:
    crafts(monkeypatch, SECOND)
    fake = FakePipeline(with_documents=False)
    report = await run_coverage_enrichment(FakeSession(), fake.as_pipeline(), day_started_at=DAY)
    assert report.crafts[0].questions == 5
    assert (fake.composed, stored) == (0, [])


async def test_an_unexpected_error_closes_the_job_and_propagates(
    monkeypatch: pytest.MonkeyPatch, stored: list[tuple[str, Any]]
) -> None:
    crafts(monkeypatch, FIRST)
    fake = FakePipeline(failures={"Kutch-Ajrakh": KeyError("bug")})
    session = FakeSession()
    with pytest.raises(KeyError):
        await run_coverage_enrichment(session, fake.as_pipeline(), day_started_at=DAY)
    (finished,) = session.finished()
    assert finished["status"] == "FAILED"


def test_a_request_id_scope_tags_and_restores() -> None:
    assert current_request_id() is None
    with request_id_scope("enrichment-abc12345"):
        assert current_request_id() == "enrichment-abc12345"
    assert current_request_id() is None
    with pytest.raises(ValueError), request_id_scope("bad id!"):
        pass
