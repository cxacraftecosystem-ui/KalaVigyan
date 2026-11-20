from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import ColumnElement, and_, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure
from app.curation.matching import match_key, quote_found
from app.models import ClaimSource, Source, SourceUpkeep
from app.research.fetcher import Fetcher, FetchRefused, FetchRequest

from .upkeep_records import FAILED, record_fetch

__all__ = [
    "FAILING_RECHECK_AFTER",
    "FETCHER_OUTAGE_MIN",
    "QUOTE_RECHECK_AFTER",
    "QUOTE_SOURCES_PER_NIGHT",
    "CitedQuote",
    "DueSource",
    "QuotesReport",
    "SourceCheck",
    "check_source",
    "quote_verdicts",
    "recheck_quotes",
    "sources_due",
]

QUOTE_SOURCES_PER_NIGHT = 50
QUOTE_RECHECK_AFTER = timedelta(days=30)
FAILING_RECHECK_AFTER = timedelta(days=7)
FETCHER_OUTAGE_MIN = 3
HTTPS_PREFIX = "https://"
PASS = "PASS"
FAIL = "FAIL"
BAD_URL = "BAD_URL"
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class CitedQuote:
    claim_source_id: uuid.UUID
    quote: str


@dataclass(frozen=True)
class DueSource:
    source_id: uuid.UUID
    url: str
    quotes: tuple[CitedQuote, ...]


@dataclass(frozen=True)
class SourceCheck:
    source_id: uuid.UUID
    outcome: str
    problem: str | None = None
    verdicts: dict[uuid.UUID, str] = field(default_factory=dict)
    undecided: int = 0
    unreachable: bool = False


@dataclass
class QuotesReport:
    checks: list[SourceCheck] = field(default_factory=list)
    fetcher_unavailable: bool = False

    def as_dict(self) -> dict[str, Any]:
        verdicts = [verdict for check in self.checks for verdict in check.verdicts.values()]
        return {
            "sourcesChecked": len(self.checks),
            "fetched": self._count("FETCHED"),
            "refused": self._count("REFUSED"),
            "unreachable": self._count("FAILED"),
            "quotesPassed": verdicts.count(PASS),
            "quotesFailed": verdicts.count(FAIL),
            "quotesUndecided": sum(check.undecided for check in self.checks),
            "fetcherUnavailable": self.fetcher_unavailable,
        }

    def _count(self, outcome: str) -> int:
        return sum(1 for check in self.checks if check.outcome == outcome)


def quote_verdicts(text: str, *, truncated: bool, quotes: Sequence[CitedQuote]) -> dict[uuid.UUID, str]:
    key = match_key(text)
    verdicts: dict[uuid.UUID, str] = {}
    for cited in quotes:
        if quote_found(cited.quote, key):
            verdicts[cited.claim_source_id] = PASS
        elif not truncated:
            verdicts[cited.claim_source_id] = FAIL
    return verdicts


async def check_source(fetcher: Fetcher, due: DueSource) -> SourceCheck:
    try:
        page = await fetcher.fetch(FetchRequest(url=due.url))
    except FetchRefused as refused:
        return SourceCheck(due.source_id, "REFUSED", refused.reason)
    except ValidationError:
        return SourceCheck(due.source_id, "REFUSED", BAD_URL)
    except ExternalFailure as failure:
        problem = f"{failure.kind} {failure.status}" if failure.status else failure.kind
        unreachable = failure.kind == UNAVAILABLE and failure.status is None
        return SourceCheck(due.source_id, "FAILED", problem, unreachable=unreachable)
    verdicts = quote_verdicts(page.text, truncated=page.truncated, quotes=due.quotes)
    return SourceCheck(due.source_id, "FETCHED", verdicts=verdicts, undecided=len(due.quotes) - len(verdicts))


def fetcher_down(checks: Sequence[SourceCheck]) -> bool:
    return len(checks) >= FETCHER_OUTAGE_MIN and all(check.unreachable for check in checks)


async def sources_due(session: AsyncSession, *, now: datetime, limit: int) -> list[DueSource]:
    statement = (
        select(Source.id, Source.url)
        .outerjoin(SourceUpkeep, SourceUpkeep.sourceId == Source.id)
        .where(
            Source.url.startswith(HTTPS_PREFIX),
            exists().where(ClaimSource.sourceId == Source.id),
            _due(now),
        )
        .order_by(SourceUpkeep.checkedAt.asc().nulls_first(), Source.id)
        .limit(limit)
    )
    rows = (await session.execute(statement)).all()
    quotes = await _quotes_of(session, [row.id for row in rows])
    return [DueSource(row.id, row.url, tuple(quotes.get(row.id, ()))) for row in rows]


def _due(now: datetime) -> ColumnElement[bool]:
    failing = or_(
        SourceUpkeep.outcome == FAILED,
        exists().where(ClaimSource.sourceId == Source.id, ClaimSource.quoteCheck == FAIL),
    )
    return or_(
        SourceUpkeep.checkedAt.is_(None),
        SourceUpkeep.checkedAt < now - QUOTE_RECHECK_AFTER,
        and_(failing, SourceUpkeep.checkedAt < now - FAILING_RECHECK_AFTER),
    )


async def recheck_quotes(
    session: AsyncSession, fetcher: Fetcher, *, now: datetime, limit: int = QUOTE_SOURCES_PER_NIGHT
) -> QuotesReport:
    report = QuotesReport()
    for due in await sources_due(session, now=now, limit=limit):
        report.checks.append(await check_source(fetcher, due))
    if fetcher_down(report.checks):
        report.fetcher_unavailable = True
        return report
    for check in report.checks:
        await _record_verdicts(session, check.verdicts, now)
        await record_fetch(session, check.source_id, outcome=check.outcome, problem=check.problem, now=now)
    await session.commit()
    return report


async def _record_verdicts(session: AsyncSession, verdicts: dict[uuid.UUID, str], now: datetime) -> None:
    for verdict in (PASS, FAIL):
        ids = [claim_source_id for claim_source_id, found in verdicts.items() if found == verdict]
        if ids:
            await session.execute(
                update(ClaimSource).where(ClaimSource.id.in_(ids)).values(quoteCheck=verdict, checkedAt=now)
            )


async def _quotes_of(session: AsyncSession, source_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[CitedQuote]]:
    if not source_ids:
        return {}
    rows = await session.execute(
        select(ClaimSource.id, ClaimSource.sourceId, ClaimSource.quote)
        .where(ClaimSource.sourceId.in_(source_ids), ClaimSource.quote.is_not(None))
        .order_by(ClaimSource.id)
    )
    found: dict[uuid.UUID, list[CitedQuote]] = defaultdict(list)
    for claim_source_id, source_id, quote in rows.all():
        found[source_id].append(CitedQuote(claim_source_id, quote))
    return found
