from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, time
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel

from app.research.coverage import FieldCoverage
from app.retrieval.eval_floors import EvalFloors, FloorCheck, eval_floors, floor_checks
from app.retrieval.evaluation import ORDERS
from app.services import write_back_filing_store
from app.services.admin_spend import spend_by_day_and_task
from app.services.coverage import COVERAGE_CLAIMS_MIN, craft_coverage, subject_coverage
from app.services.mcp_activity import ActivityAsk, read_activity
from app.services.open_work_subjects import curated_craft_subjects
from app.services.source_titles import junk_titled, producer_authored
from app.services.upkeep_hidden import last_hidden_facts

from .mcp_report_pages import (
    COVERAGE,
    EVALUATIONS,
    FILING,
    HIDDEN_FACTS,
    MCP_ACTIVITY,
    SOURCES,
    SPEND,
    ReportAsk,
    ReportPage,
    page_rows,
    paged,
)
from .mcp_tool_base import ToolContext

__all__ = [
    "READERS",
    "activity_report",
    "coverage_report",
    "evaluations_report",
    "filing_report",
    "floor_rows",
    "hidden_facts_report",
    "sources_report",
    "spend_report",
]

ANSWERS, RETRIEVAL = "answers", "retrieval"
TITLE, AUTHORS = "title", "authors"
COVERAGE_SAID = (
    "Field standings of each craft ({total} in all): a field is covered at {least} cited facts, thin below "
    "that and missing at none."
)
NO_HIDDEN_COUNT = "No count of hidden facts is stored yet; the nightly upkeep writes it."
HIDDEN_SAID = (
    "Counted at {at}: crafts holding facts readers cannot see, {crafts} ({reasons}); facts hidden for no "
    "known reason, {unexplained}."
)
FILING_SAID = (
    "Live-research facts, oldest first: {facts}; filed where today's rule would not file them: {moves}."
)
FILING_MAX_SAID = " The report reads at most {most} facts; narrow it by since or answer_id."
SOURCES_SAID = (
    "Sources whose title is not a work's title: {titles}; sources naming a file's producer as their "
    "author: {authors}."
)
ACTIVITY_SAID = (
    "MCP calls from {first} to {last} (India days): {calls}, of which {failed} failed; rows by tool, by "
    "client, then the newest failures, with no account named."
)
SPEND_SAID = (
    "Settled AI spend of {cost} USD from {first} to {last} (India days), by day and task, newest day first; "
    "calls still reserved are left out."
)
NOTHING_MEASURED = (
    "No answer-quality or retrieval-eval result is stored where the server can read it (each run's report is its "
    "workflow's artifact), so these are the floors alone, unmeasured."
)

Reader = Callable[[ToolContext, ReportAsk], Awaitable[ReportPage]]


async def coverage_report(context: ToolContext, ask: ReportAsk) -> ReportPage:
    if ask.craft is not None:
        found = await craft_coverage(context.session, ask.craft)
        return page_rows([_standing(found)], ask, COVERAGE_SAID.format(total=1, least=COVERAGE_CLAIMS_MIN))
    subjects = sorted(await curated_craft_subjects(context.session), key=lambda subject: subject.slug)
    window = subjects[ask.offset : ask.offset + ask.limit]
    standings = await subject_coverage(context.session, window)
    said = COVERAGE_SAID.format(total=len(subjects), least=COVERAGE_CLAIMS_MIN)
    return paged(
        [_standing(standings[subject.id]) for subject in window], ask, total=len(subjects), message=said
    )


async def hidden_facts_report(context: ToolContext, ask: ReportAsk) -> ReportPage:
    stored = await last_hidden_facts(context.session)
    if stored is None:
        return page_rows([], ask, NO_HIDDEN_COUNT)
    rows = [row for row in stored.get("perCraft", []) if ask.craft is None or row.get("craft") == ask.craft]
    reasons = ", ".join(f"{reason} {count}" for reason, count in sorted(stored.get("byReason", {}).items()))
    said = HIDDEN_SAID.format(
        at=stored.get("countedAt"),
        crafts=stored.get("crafts", 0),
        reasons=reasons,
        unexplained=stored.get("unexplained", 0),
    )
    return page_rows(rows, ask, said)


async def filing_report(context: ToolContext, ask: ReportAsk) -> ReportPage:
    since = datetime.combine(ask.since, time.min, tzinfo=UTC) if ask.since is not None else None
    rows = await write_back_filing_store.filing_report(
        context.session, context.index, answer_id=ask.answer_id, since=since
    )
    said = FILING_SAID.format(facts=len(rows), moves=sum(1 for row in rows if row.moves))
    if len(rows) >= write_back_filing_store.FILING_REPORT_MAX:
        said += FILING_MAX_SAID.format(most=write_back_filing_store.FILING_REPORT_MAX)
    return page_rows([row.as_dict() | {"moves": row.moves} for row in rows], ask, said)


async def sources_report(context: ToolContext, ask: ReportAsk) -> ReportPage:
    titles = sorted(await junk_titled(context.session), key=lambda found: found.id)
    authors = await producer_authored(context.session)
    rows = [
        *(found.as_dict() | {"problem": TITLE} for found in titles),
        *(found.as_dict() | {"problem": AUTHORS} for found in authors),
    ]
    return page_rows(rows, ask, SOURCES_SAID.format(titles=len(titles), authors=len(authors)))


async def activity_report(context: ToolContext, ask: ReportAsk) -> ReportPage:
    activity = await read_activity(context.session, ActivityAsk(days=ask.days), now=ask.now)
    rows = [
        *(_kinded("tool", tool) for tool in activity.tools),
        *(_kinded("client", client) for client in activity.clients),
        *(_kinded("failure", failure) for failure in activity.failures),
    ]
    failed = sum(point.tool_errors + point.protocol_errors for point in activity.series)
    said = ACTIVITY_SAID.format(
        calls=failed + sum(point.ok for point in activity.series),
        first=activity.first_day.isoformat(),
        last=activity.last_day.isoformat(),
        failed=failed,
    )
    return page_rows(rows, ask, said)


async def spend_report(context: ToolContext, ask: ReportAsk) -> ReportPage:
    spend = await spend_by_day_and_task(
        context.session, days=ask.days, now=ask.now, offset=ask.offset, limit=ask.limit
    )
    said = SPEND_SAID.format(
        cost=float(spend.cost_usd), first=spend.first_day.isoformat(), last=spend.last_day.isoformat()
    )
    return paged([row.as_dict() for row in spend.rows], ask, total=spend.total, message=said)


async def evaluations_report(context: ToolContext, ask: ReportAsk) -> ReportPage:
    return page_rows(floor_rows(eval_floors()), ask, NOTHING_MEASURED)


def floor_rows(floors: EvalFloors) -> list[dict[str, Any]]:
    answers = [_floor(ANSWERS, check) for check in floor_checks({}, floors.answers.named())]
    retrieval = [
        _floor(RETRIEVAL, check)
        for name in floors.retrieval
        for order in ORDERS
        for check in floor_checks({}, floors.retrieval_floors(name, order), prefix=f"{name}.{order}.")
    ]
    return [*answers, *retrieval]


def _standing(coverage: FieldCoverage) -> dict[str, Any]:
    return {
        "craft": coverage.subject_slug,
        "kind": coverage.subject_kind,
        "name": coverage.name,
        "claims": coverage.claims,
        "sources": coverage.sources,
        "covered": list(coverage.covered),
        "thin": list(coverage.thin),
        "missing": list(coverage.missing),
    }


def _kinded(kind: str, row: BaseModel) -> dict[str, Any]:
    return {"kind": kind, **row.model_dump(mode="json", by_alias=True)}


def _floor(suite: str, check: FloorCheck) -> dict[str, Any]:
    passes = None if check.value is None else check.held
    return {
        "suite": suite,
        "measure": check.measure,
        "floor": check.floor,
        "measured": check.value,
        "passes": passes,
    }


READERS: Mapping[str, Reader] = MappingProxyType(
    {
        COVERAGE: coverage_report,
        HIDDEN_FACTS: hidden_facts_report,
        FILING: filing_report,
        SOURCES: sources_report,
        MCP_ACTIVITY: activity_report,
        SPEND: spend_report,
        EVALUATIONS: evaluations_report,
    }
)
