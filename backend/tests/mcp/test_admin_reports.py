import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.api.mcp_report_pages import ReportAsk, ReportPage, bounded_row, fitting, page_rows, paged
from app.api.mcp_report_reads import floor_rows
from app.api.mcp_report_tools import NOT_ADMIN, REPORT_TOOLS, AdminReportArguments, report_ask
from app.api.mcp_tools import ToolContext, answer
from app.core.errors import InvalidInput
from app.models import User
from app.retrieval.eval_floors import parse_floors
from app.services.craft_resolver import CraftIndexStore

SITE = "https://kalavigyan.example"
NO_SESSION: Any = None
NOW = datetime(2026, 11, 23, 6, 0, tzinfo=UTC)
ANSWER = uuid.UUID("0d000000-0000-4000-8000-0000000000a1")
READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}
ARGUMENT_NAMES = {"report", "craft_slug", "since", "answer_id", "days", "cursor", "limit"}
SEVEN = [{"n": n} for n in range(7)]
CUT_SAID = " Lists longer than 20 are cut to their first 20; an item's cut gives each one's full length."
PAGE_SAID = " This page stops at 8 rows to keep the reply small; next_cursor goes on from there."


def context(*scopes: str, role: str | None = None) -> ToolContext:
    user = None
    if role is not None:
        user = User(id=uuid.uuid4(), name="Meera Iyer", email="meera@example.org", role=role)
    return ToolContext(
        session=NO_SESSION, index=CraftIndexStore(), site=SITE, user=user, scopes=frozenset(scopes)
    )


async def listed(tool_context: ToolContext) -> dict[str, dict[str, Any]]:
    reply = await answer({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, tool_context)
    assert reply is not None and "result" in reply, reply
    return {tool["name"]: tool for tool in reply["result"]["tools"]}


async def called(arguments: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
    params = {"name": "admin_reports", "arguments": arguments}
    reply = await answer({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": params}, tool_context)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


async def test_the_reports_are_listed_only_to_a_connection_with_the_review_scope() -> None:
    assert "admin_reports" not in await listed(context("read"))
    assert "admin_reports" not in await listed(context("read", "ask", "contribute"))
    tool = (await listed(context("read", "review")))["admin_reports"]
    assert tool["annotations"] == READ_ONLY
    assert tool["_meta"]["kalavigyan/group"] == "admin"
    assert set(tool["inputSchema"]["properties"]) == ARGUMENT_NAMES
    assert tool["inputSchema"]["required"] == ["report"]
    assert len(tool["description"]) <= 520


@pytest.mark.parametrize("role", ["RESEARCHER", "PROFESSOR"])
async def test_an_account_below_admin_is_refused_even_with_the_review_scope(role: str) -> None:
    result = await called({"report": "evaluations"}, context("read", "review", role=role))
    assert result == {"content": [{"type": "text", "text": NOT_ADMIN}], "isError": True}


async def test_the_tool_itself_refuses_a_connection_with_no_account() -> None:
    with pytest.raises(InvalidInput, match="for Admins and Master Admins"):
        await REPORT_TOOLS[0].run(context("read", "review"), AdminReportArguments(report="evaluations"))


async def test_an_admin_without_the_review_scope_is_refused_before_the_tool_runs() -> None:
    result = await called({"report": "evaluations"}, context("read", role="ADMIN"))
    assert result["isError"] is True
    assert "review scope" in result["content"][0]["text"]


@pytest.mark.parametrize("role", ["ADMIN", "MASTER_ADMIN"])
async def test_an_admin_reads_the_floors_with_nothing_measured(role: str) -> None:
    result = await called({"report": "evaluations", "limit": 50}, context("read", "review", role=role))
    assert result["isError"] is False
    report = result["structuredContent"]
    assert report["report"] == "evaluations" and report["next_cursor"] is None
    assert report["total"] == len(report["items"]) > 0
    assert report["items"][0]["suite"] == "answers" and report["items"][0]["measure"] == "judgeMean"
    assert all(item["measured"] is None and item["passes"] is None for item in report["items"])
    assert report["message"].startswith("No answer-quality or retrieval-eval result is stored")


async def test_an_unknown_report_and_a_filter_the_report_does_not_read_are_refused_by_name() -> None:
    admin = context("read", "review", role="ADMIN")
    unknown = await called({"report": "weekly_digest"}, admin)
    assert unknown["isError"] is True and unknown["content"][0]["text"].startswith("report:")
    unfit = await called({"report": "sources", "craft_slug": "Kutch-Ajrakh"}, admin)
    assert unfit["isError"] is True
    assert unfit["content"][0]["text"].endswith("the sources report takes no craft_slug")


@pytest.mark.parametrize(
    "given",
    [
        {"report": "weekly_digest"},
        {"report": "spend", "limit": 51},
        {"report": "spend", "limit": 0},
        {"report": "spend", "days": 14},
        {"report": "sources", "cursor": "next"},
        {"report": "sources", "cursor": "-5"},
        {"report": "sources", "craft_slug": "Kutch-Ajrakh"},
        {"report": "coverage", "days": 7},
        {"report": "spend", "since": "2026-11-01"},
        {"report": "mcp_activity", "answer_id": str(ANSWER)},
        {"report": "filing", "page": 2},
    ],
)
def test_the_arguments_refuse_what_no_report_reads(given: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        AdminReportArguments.model_validate(given)


def test_the_arguments_become_one_ask_with_the_cursor_as_an_offset() -> None:
    filing = AdminReportArguments.model_validate(
        {"report": "filing", "since": "2026-11-01", "answer_id": str(ANSWER), "cursor": "50", "limit": 50}
    )
    assert report_ask(filing, now=NOW) == ReportAsk(
        now=NOW, since=date(2026, 11, 1), answer_id=ANSWER, days=30, offset=50, limit=50
    )
    spend = AdminReportArguments.model_validate({"report": "spend"})
    assert report_ask(spend, now=NOW) == ReportAsk(now=NOW, days=30, offset=0, limit=25)
    activity = AdminReportArguments.model_validate({"report": "mcp_activity", "days": 180})
    assert report_ask(activity, now=NOW).days == 180


def test_a_page_holds_at_most_its_limit_and_points_at_the_next_row() -> None:
    assert page_rows(SEVEN, ReportAsk(now=NOW, limit=3), "Seven.") == ReportPage(
        [{"n": 0}, {"n": 1}, {"n": 2}], 7, "3", "Seven."
    )
    assert page_rows(SEVEN, ReportAsk(now=NOW, offset=3, limit=3), "Seven.") == ReportPage(
        [{"n": 3}, {"n": 4}, {"n": 5}], 7, "6", "Seven."
    )
    assert page_rows(SEVEN, ReportAsk(now=NOW, offset=6, limit=3), "Seven.") == ReportPage(
        [{"n": 6}], 7, None, "Seven."
    )
    assert page_rows(SEVEN, ReportAsk(now=NOW, offset=9, limit=3), "Seven.") == ReportPage(
        [], 7, None, "Seven."
    )


def test_a_page_read_from_the_database_keeps_its_offset_and_the_whole_count() -> None:
    window = [{"n": 3}, {"n": 4}]
    assert paged(window, ReportAsk(now=NOW, offset=3, limit=2), total=7, message="M.") == ReportPage(
        window, 7, "5", "M."
    )
    assert paged(window, ReportAsk(now=NOW, offset=5, limit=2), total=7, message="M.") == ReportPage(
        window, 7, None, "M."
    )


def test_a_reply_keeps_the_rows_that_fit_its_bytes_and_always_one() -> None:
    rows = [{"a": "xx"}] * 3
    assert fitting(rows, 33) == 3
    assert fitting(rows, 32) == 2
    assert fitting(rows, 5) == 1
    assert fitting([], 5) == 0


def test_a_page_too_large_for_the_reply_stops_early_and_says_so() -> None:
    rows = [{"words": ["a" * 300] * 20} for _ in range(10)]
    page = page_rows(rows, ReportAsk(now=NOW, limit=10), "Big rows.")
    assert len(page.items) == 8
    assert (page.total, page.next_cursor) == (10, "8")
    assert page.message == "Big rows." + PAGE_SAID


def test_a_row_cuts_long_lists_and_long_texts_and_says_how_long_each_list_was() -> None:
    row = {
        "id": "s1",
        "authors": [f"author {n}" for n in range(22)],
        "title": "t" * 301,
        "hidden": {"HELD": 2},
        "citations": 0,
    }
    assert bounded_row(row) == {
        "id": "s1",
        "authors": [f"author {n}" for n in range(20)],
        "title": "t" * 299 + "…",
        "hidden": {"HELD": 2},
        "citations": 0,
        "cut": {"authors": 22},
    }
    assert bounded_row({"title": "t" * 300, "authors": ["a"] * 20}) == {
        "title": "t" * 300,
        "authors": ["a"] * 20,
    }
    assert page_rows([row], ReportAsk(now=NOW), "One source.").message == "One source." + CUT_SAID


def test_each_floor_becomes_a_row_with_nothing_measured() -> None:
    floors = parse_floors(
        {
            "version": 2,
            "retrieval": {
                "handWritten": {"reranked": {"recallAt5": 0.93}, "fused": {"meanReciprocalRank": 0.88}}
            },
            "answers": {"judgeMean": 0.76, "rubricMean": None},
        }
    )
    assert floor_rows(floors) == [
        {"suite": "answers", "measure": "judgeMean", "floor": 0.76, "measured": None, "passes": None},
        {
            "suite": "retrieval",
            "measure": "handWritten.reranked.recallAt5",
            "floor": 0.93,
            "measured": None,
            "passes": None,
        },
        {
            "suite": "retrieval",
            "measure": "handWritten.fused.meanReciprocalRank",
            "floor": 0.88,
            "measured": None,
            "passes": None,
        },
    ]
