import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Claim, ClaimSource, Concept, Craft, Source
from app.research.retrieval import RESEARCHER_CHUNK_ACL, RESTRICTED_SENSITIVITY
from app.retrieval.indexing import replace_source_chunks

__all__ = [
    "CLOSED",
    "CONCEPT",
    "CRAFT",
    "FAILING",
    "FIELD",
    "HELD",
    "HIDDEN",
    "RESTRICTED",
    "SECRET",
    "SLUG",
    "Cite",
    "key",
    "seeded_facts",
]

SLUG = "Reader-Facts-Test-Craft"
FIELD = "HEALTH"
CLOSED_TEXT = (
    "Most textile dyes used by the hand block printing units of Sanganer have not been evaluated for "
    "their health impact, the 2007 study says."
)
CLOSED_QUOTE = "Most textile dyes used by the hand block printing units of Sanganer have not been evaluated"
OPEN_QUOTE = "eleven groundwater samples from various locations of Sanganer were found polluted"
LOST_QUOTE = "a sentence the page no longer holds anywhere at all"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-reader-facts/{name}")


CRAFT, CONCEPT, HIDDEN_CONCEPT = key("craft"), key("concept"), key("hidden-concept")
STUDY, OPEN_PAGE, LETTER = key("study"), key("open-page"), key("letter")
CLOSED, HELD, FAILING = key("closed"), key("held"), key("failing")
HIDDEN, SECRET, RESTRICTED = key("hidden"), key("secret"), key("restricted")


@dataclass(frozen=True)
class Cite:
    source_id: uuid.UUID
    quote: str | None
    check: str = "PASS"


async def seeded_facts() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await _seed(session)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def _seed(session: AsyncSession) -> None:
    session.add(Craft(id=CRAFT, slug=SLUG, name="Reader Facts Test Craft"))
    await session.flush()
    session.add_all(
        [
            Concept(id=CONCEPT, craftId=CRAFT, type="MATERIAL", name="Textile dyes"),
            Concept(
                id=HIDDEN_CONCEPT,
                craftId=CRAFT,
                type="MATERIAL",
                name="A guarded recipe",
                sensitivity=RESTRICTED_SENSITIVITY,
            ),
            Source(id=STUDY, kind="PAPER", title="Genotoxicity of textile dyes used in Sanganer"),
            Source(id=OPEN_PAGE, kind="WEB_PAGE", title="Groundwater of Sanganer", licence="CC BY 4.0"),
            Source(id=LETTER, kind="PAPER", title="A restricted letter", sensitivity=RESTRICTED_SENSITIVITY),
        ]
    )
    await session.flush()
    await replace_source_chunks(session, STUDY, CLOSED_TEXT, acl=RESEARCHER_CHUNK_ACL)
    await fact(session, CLOSED, Cite(STUDY, CLOSED_QUOTE))
    await fact(session, HELD, Cite(OPEN_PAGE, LOST_QUOTE, check="FAIL"))
    await fact(session, FAILING, Cite(OPEN_PAGE, OPEN_QUOTE), Cite(STUDY, LOST_QUOTE, check="FAIL"))
    await fact(session, HIDDEN, Cite(OPEN_PAGE, OPEN_QUOTE), concept=HIDDEN_CONCEPT)
    await fact(session, SECRET, Cite(LETTER, None))
    await fact(session, RESTRICTED, Cite(OPEN_PAGE, OPEN_QUOTE), sensitivity=RESTRICTED_SENSITIVITY)


async def fact(
    session: AsyncSession,
    claim_id: uuid.UUID,
    *cites: Cite,
    concept: uuid.UUID = CONCEPT,
    sensitivity: str = "OPEN",
) -> None:
    session.add(
        Claim(
            id=claim_id,
            subjectType="CONCEPT",
            subjectId=concept,
            predicate="states",
            text=f"Sanganer's dyes, as fact {claim_id.hex[:8]} states, were tested in 2007.",
            evidenceLevel="PROVISIONAL",
            origin="CONTRIBUTION",
            status="APPROVED",
            field=FIELD,
            sensitivity=sensitivity,
        )
    )
    await session.flush()
    session.add_all(
        ClaimSource(
            claimId=claim_id,
            sourceId=cite.source_id,
            quote=cite.quote,
            quoteCheck=cite.check if cite.quote else "NA",
        )
        for cite in cites
    )
    await session.flush()
