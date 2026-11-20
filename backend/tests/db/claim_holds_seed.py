import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, ClaimSource, Concept, Craft, Source, SourceUpkeep

from .testimony_seed import rolled_back_session

__all__ = [
    "ARCHIVED_ONLY",
    "CHECKED",
    "CRAFT",
    "FAILING",
    "HELD",
    "HOST",
    "LOST_QUOTE",
    "ROTTEN_ONLY",
    "SLUG",
    "SOUND",
    "SOURCES",
    "STATEMENT",
    "held_session",
    "quote_row",
]

NOW = datetime(2026, 11, 20, 0, 30, tzinfo=UTC)
CHECKED = NOW - timedelta(days=1)
DOSSIER_CHECKED = NOW - timedelta(days=60)
SLUG = "Claim-Holds-Test-Craft"
HOST = "https://claim-holds-test.example.org"
STATEMENT = "Ajrakh cloth is dipped in the indigo vat four times, the colour deepening with each dip."
LOST_QUOTE = "The cloth is dipped in indigo four times at Dhamadka"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-claim-holds/{name}")


CRAFT, CONCEPT = key("craft"), key("concept")
HELD, FAILING, SOUND, ROTTEN_ONLY, ARCHIVED_ONLY = (
    key("held"),
    key("failing"),
    key("sound"),
    key("rotten-only"),
    key("archived-only"),
)
SOURCES = {name: key(f"source-{name}") for name in ("one", "two", "rotten", "archived")}


def quote_row(claim: uuid.UUID, source: str, n: int) -> uuid.UUID:
    return key(f"quote-{claim}-{source}-{n}")


async def held_session() -> AsyncIterator[AsyncSession]:
    async for session in rolled_back_session():
        await _seed(session)
        yield session


async def _seed(session: AsyncSession) -> None:
    session.add(Craft(id=CRAFT, slug=SLUG, name="Claim Holds Test Craft", stateOfPractice=["Gujarat"]))
    await session.flush()
    session.add(Concept(id=CONCEPT, craftId=CRAFT, type="MATERIAL", name="Indigo"))
    for name, source_id in SOURCES.items():
        session.add(Source(id=source_id, kind="WEB_PAGE", title=f"Holds source {name}", url=f"{HOST}/{name}"))
    await session.flush()
    session.add(SourceUpkeep(sourceId=SOURCES["rotten"], checkedAt=CHECKED, outcome="FAILED", failures=3))
    session.add(
        SourceUpkeep(
            sourceId=SOURCES["archived"],
            checkedAt=CHECKED,
            outcome="FAILED",
            failures=4,
            archiveTriedAt=DOSSIER_CHECKED,
            archivedAt=DOSSIER_CHECKED,
            archiveUrl=f"https://web.archive.org/web/20260920000000/{HOST}/archived",
        )
    )
    for claim_id in (HELD, FAILING, SOUND, ROTTEN_ONLY, ARCHIVED_ONLY):
        session.add(_claim(claim_id))
    await session.flush()
    for claim_id, source, check in (
        (HELD, "one", "FAIL"),
        (HELD, "two", "FAIL"),
        (FAILING, "one", "FAIL"),
        (FAILING, "two", "PASS"),
        (SOUND, "one", "PASS"),
        (ROTTEN_ONLY, "rotten", "PASS"),
        (ARCHIVED_ONLY, "archived", "PASS"),
    ):
        session.add(_cited(claim_id, source, check))
    await session.flush()


def _claim(claim_id: uuid.UUID, **changes: Any) -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=CONCEPT,
        predicate="states",
        text=STATEMENT,
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
        field="CHEMISTRY",
        **changes,
    )


def _cited(claim_id: uuid.UUID, source: str, check: str) -> ClaimSource:
    return ClaimSource(
        id=quote_row(claim_id, source, 0),
        claimId=claim_id,
        sourceId=SOURCES[source],
        quote=f"{LOST_QUOTE} ({source})",
        locator="p. 1",
        quoteCheck=check,
        checkedAt=CHECKED,
    )
