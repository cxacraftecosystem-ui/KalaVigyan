import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.mcp_report_pages import ReportAsk
from app.api.mcp_report_reads import hidden_facts_report, sources_report, spend_report
from app.api.mcp_tool_base import ToolContext
from app.models import Source, UsageEvent, User
from app.services.admin_spend import SpendRow, spend_by_day_and_task
from app.services.app_settings import set_value
from app.services.craft_resolver import CraftIndexStore
from app.services.upkeep_hidden import HIDDEN_FACTS_SETTING

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

SITE = "https://kalavigyan.example"
NOW = datetime(2031, 3, 10, 12, 0, tzinfo=UTC)
SETTLED = (
    ("COMPOSE", "OK", "0.500000", datetime(2031, 3, 10, 10, 0, tzinfo=UTC)),
    ("COMPOSE", "OK", "0.250000", datetime(2031, 3, 10, 11, 0, tzinfo=UTC)),
    ("PLAN", "OK", "0.100000", datetime(2031, 3, 9, 20, 0, tzinfo=UTC)),
    ("EMBED", "ERROR", "0.002000", datetime(2031, 3, 9, 18, 0, tzinfo=UTC)),
    ("COMPOSE", "OK", "9.000000", datetime(2031, 3, 3, 18, 0, tzinfo=UTC)),
    ("PLAN", "OK", "5.000000", datetime(2031, 3, 10, 19, 0, tzinfo=UTC)),
)
RESERVED_AT = datetime(2031, 3, 10, 11, 30, tzinfo=UTC)
JUNK_TITLE = "IMG_2041.pdf"
JUNK_URL = "https://example.org/files/IMG_2041.pdf"
STUDY_TITLE = "Mutagenicity assessment of textile dyes from Sanganer (Rajasthan)"
KUTCH_UNEXPLAINED = "0d000000-0000-4000-8000-0000000000c1"
HIDDEN = {
    "countedAt": "2031-03-10T00:30:00+00:00",
    "crafts": 2,
    "byReason": {"HELD": 3, "RESTRICTED_FACT": 0, "HIDDEN_CONCEPT": 0, "NO_SHOWN_SOURCE": 1},
    "unexplained": 1,
    "craftsUnexplained": ["Kutch-Ajrakh"],
    "perCraft": [
        {"craft": "Bagru-Prints", "approved": 40, "hidden": {"HELD": 2}, "unexplained": []},
        {
            "craft": "Kutch-Ajrakh",
            "approved": 60,
            "hidden": {"HELD": 1, "NO_SHOWN_SOURCE": 1},
            "unexplained": [KUTCH_UNEXPLAINED],
        },
    ],
}


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-admin-reports/{name}")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        yield opened


def admin_context(session: AsyncSession) -> ToolContext:
    admin = User(id=uuid.uuid4(), name="Meera Iyer", email="meera@example.org", role="ADMIN")
    return ToolContext(
        session=session, index=CraftIndexStore(), site=SITE, user=admin, scopes=frozenset({"read", "review"})
    )


async def spent(session: AsyncSession) -> None:
    session.add_all(
        UsageEvent(task=task, outcome=outcome, costUsd=Decimal(cost), createdAt=at)
        for task, outcome, cost, at in SETTLED
    )
    session.add(
        UsageEvent(
            task="COMPOSE",
            outcome="RESERVED",
            costUsd=Decimal(0),
            estimatedCostUsd=Decimal("2.000000"),
            createdAt=RESERVED_AT,
        )
    )
    await session.flush()


async def every_source_row(context: ToolContext) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = await sources_report(context, ReportAsk(now=NOW, offset=offset, limit=50))
        assert len(page.items) <= 50
        rows.extend(page.items)
        if page.next_cursor is None:
            return rows, page.total
        assert int(page.next_cursor) == offset + len(page.items)
        offset = int(page.next_cursor)


async def test_spend_sums_only_settled_costs_by_india_day_and_task(session: AsyncSession) -> None:
    await spent(session)
    week = await spend_by_day_and_task(session, days=7, now=NOW, offset=0, limit=50)
    assert (week.first_day, week.last_day) == (date(2031, 3, 4), date(2031, 3, 10))
    assert week.rows == [
        SpendRow(date(2031, 3, 10), "COMPOSE", 2, Decimal("0.750000")),
        SpendRow(date(2031, 3, 10), "PLAN", 1, Decimal("0.100000")),
        SpendRow(date(2031, 3, 9), "EMBED", 1, Decimal("0.002000")),
    ]
    assert (week.total, week.cost_usd) == (3, Decimal("0.852000"))
    today = await spend_by_day_and_task(session, days=1, now=NOW, offset=0, limit=50)
    assert [(row.task, row.calls) for row in today.rows] == [("COMPOSE", 2), ("PLAN", 1)]
    assert (today.total, today.cost_usd) == (2, Decimal("0.850000"))


async def test_the_spend_report_pages_its_rows_newest_day_first(session: AsyncSession) -> None:
    await spent(session)
    context = admin_context(session)
    first = await spend_report(context, ReportAsk(now=NOW, days=7, limit=2))
    assert first.items == [
        {"day": "2031-03-10", "task": "COMPOSE", "calls": 2, "costUsd": 0.75},
        {"day": "2031-03-10", "task": "PLAN", "calls": 1, "costUsd": 0.1},
    ]
    assert (first.total, first.next_cursor) == (3, "2")
    assert first.message.startswith("Settled AI spend of 0.852 USD from 2031-03-04 to 2031-03-10")
    rest = await spend_report(context, ReportAsk(now=NOW, days=7, offset=2, limit=2))
    assert rest.items == [{"day": "2031-03-09", "task": "EMBED", "calls": 1, "costUsd": 0.002}]
    assert (rest.total, rest.next_cursor) == (3, None)


async def test_the_sources_report_lists_a_junk_title_and_a_producer_author_across_its_pages(
    session: AsyncSession,
) -> None:
    session.add_all(
        [
            Source(id=key("junk"), kind="OTHER", title=JUNK_TITLE, url=JUNK_URL),
            Source(id=key("sys"), kind="OTHER", title=STUDY_TITLE, authors=["sys"]),
            Source(id=key("named"), kind="PAPER", title=STUDY_TITLE, authors=["Nupur Mathur"]),
        ]
    )
    await session.flush()
    rows, total = await every_source_row(admin_context(session))
    listed = {(row["id"], row["problem"]): row for row in rows}
    assert len(listed) == len(rows) == total
    assert listed[(str(key("junk")), "title")] == {
        "id": str(key("junk")),
        "title": JUNK_TITLE,
        "url": JUNK_URL,
        "citations": 0,
        "problem": "title",
    }
    assert listed[(str(key("sys")), "authors")] == {
        "id": str(key("sys")),
        "title": STUDY_TITLE,
        "url": None,
        "authors": ["sys"],
        "citations": 0,
        "problem": "authors",
    }
    assert not {problem for source, problem in listed if source == str(key("named"))}


async def test_the_hidden_facts_report_reads_the_night_s_count_for_one_craft(session: AsyncSession) -> None:
    await set_value(session, HIDDEN_FACTS_SETTING, HIDDEN)
    await session.flush()
    page = await hidden_facts_report(admin_context(session), ReportAsk(now=NOW, craft="Kutch-Ajrakh"))
    assert page.items == [
        {
            "craft": "Kutch-Ajrakh",
            "approved": 60,
            "hidden": {"HELD": 1, "NO_SHOWN_SOURCE": 1},
            "unexplained": [KUTCH_UNEXPLAINED],
        }
    ]
    assert (page.total, page.next_cursor) == (1, None)
    assert page.message == (
        "Counted at 2031-03-10T00:30:00+00:00: crafts holding facts readers cannot see, 2 (HELD 3, "
        "HIDDEN_CONCEPT 0, NO_SHOWN_SOURCE 1, RESTRICTED_FACT 0); facts hidden for no known reason, 1."
    )
    whole = await hidden_facts_report(admin_context(session), ReportAsk(now=NOW, limit=1))
    assert [row["craft"] for row in whole.items] == ["Bagru-Prints"]
    assert (whole.total, whole.next_cursor) == (2, "1")
