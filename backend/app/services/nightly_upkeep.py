from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.research.embedding import TextEmbedder
from app.research.fetcher import Fetcher
from app.sources.fetcher_client import FetcherClient
from app.sources.wayback_save import WaybackSaver

from .answer_gap_refresh import AnswerGapsReport, refresh_answer_gaps
from .claim_holds import shown_held_ids
from .open_work_refresh import FieldWorkReport, refresh_field_work
from .orphan_concepts import OrphansReport, orphan_concepts, sweep_orphans
from .upkeep_allowances import AllowancesReport, sweep_allowances
from .upkeep_archive import (
    ARCHIVES_PER_NIGHT,
    ArchiveReport,
    SourceArchiver,
    archive_sources,
    sources_at_risk,
)
from .upkeep_clients import ClientsReport, abandoned_client_count, remove_abandoned_clients
from .upkeep_healing import HealingReport, heal
from .upkeep_links import rotten_count
from .upkeep_pages import (
    MONOGRAPHS_PER_NIGHT,
    MonographLoader,
    PagesReport,
    rebuild_documents,
    rebuild_monographs,
    rebuild_stale_pages,
    rotating_window,
    stale_crafts,
)
from .upkeep_quotes import QUOTE_SOURCES_PER_NIGHT, QuotesReport, recheck_quotes, sources_due

__all__ = ["UpkeepReport", "UpkeepTools", "plan_nightly_upkeep", "run_nightly_upkeep", "upkeep_tools"]


@dataclass(frozen=True)
class UpkeepTools:
    fetcher: Fetcher
    archiver: SourceArchiver
    monographs: Sequence[str]
    load_monograph: MonographLoader
    embed: TextEmbedder | None = None


def upkeep_tools(
    client: httpx.AsyncClient,
    *,
    fetcher_url: str,
    monographs: Sequence[str],
    load: MonographLoader,
    embed: TextEmbedder | None = None,
) -> UpkeepTools:
    return UpkeepTools(
        fetcher=FetcherClient(fetcher_url, client),
        archiver=WaybackSaver(client),
        monographs=tuple(monographs),
        load_monograph=load,
        embed=embed,
    )


@dataclass
class UpkeepReport:
    quotes: QuotesReport = field(default_factory=QuotesReport)
    healing: HealingReport = field(default_factory=HealingReport)
    archive: ArchiveReport = field(default_factory=ArchiveReport)
    orphans: OrphansReport = field(default_factory=OrphansReport)
    clients: ClientsReport = field(default_factory=ClientsReport)
    pages: PagesReport = field(default_factory=PagesReport)
    field_work: FieldWorkReport = field(default_factory=FieldWorkReport)
    allowances: AllowancesReport = field(default_factory=AllowancesReport)
    answer_gaps: AnswerGapsReport = field(default_factory=AnswerGapsReport)

    @property
    def ok(self) -> bool:
        return not self.pages.failed and not self.quotes.fetcher_unavailable

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "quotes": self.quotes.as_dict(),
            "healing": self.healing.as_dict(),
            "archive": self.archive.as_dict(),
            "orphans": self.orphans.as_dict(),
            "clients": self.clients.as_dict(),
            "pages": self.pages.as_dict(),
            "fieldWork": self.field_work.as_dict(),
            "allowances": self.allowances.as_dict(),
            "answerGaps": self.answer_gaps.as_dict(),
        }


async def run_nightly_upkeep(session: AsyncSession, tools: UpkeepTools, *, now: datetime) -> UpkeepReport:
    report = UpkeepReport()
    before = await shown_held_ids(session)
    report.quotes = await recheck_quotes(session, tools.fetcher, now=now)
    report.healing = await heal(session, before=before)
    report.archive = await archive_sources(session, tools.archiver, now=now)
    report.orphans = await sweep_orphans(session, now=now)
    report.clients = await remove_abandoned_clients(session, now=now)
    report.allowances = await sweep_allowances(session, now=now)
    await rebuild_monographs(session, tools.monographs, tools.load_monograph, now=now, report=report.pages)
    await rebuild_stale_pages(session, skip=frozenset(tools.monographs), report=report.pages)
    await rebuild_documents(session, report=report.pages)
    report.field_work = await refresh_field_work(session, now=now)
    report.answer_gaps = await refresh_answer_gaps(session, tools.embed, now=now)
    return report


async def plan_nightly_upkeep(
    session: AsyncSession, monographs: Sequence[str], *, now: datetime
) -> dict[str, Any]:
    due = await sources_due(session, now=now, limit=QUOTE_SOURCES_PER_NIGHT)
    at_risk = await sources_at_risk(session, now=now, limit=ARCHIVES_PER_NIGHT)
    orphans = await orphan_concepts(session, now=now)
    stale = await stale_crafts(session, skip=frozenset(monographs))
    return {
        "ok": True,
        "dryRun": True,
        "sourcesDue": len(due),
        "sourcesAtRisk": len(at_risk),
        "claimsHeld": len(await shown_held_ids(session)),
        "sourcesRotten": await rotten_count(session),
        "monographs": rotating_window(sorted(monographs), MONOGRAPHS_PER_NIGHT, now.date().toordinal()),
        "pagesStale": len(stale),
        "clientsAbandoned": await abandoned_client_count(session, now=now),
        "orphans": [orphan.as_dict() for orphan in orphans],
    }
