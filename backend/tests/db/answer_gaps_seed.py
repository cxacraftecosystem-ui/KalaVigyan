import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Answer, AnswerVerdict, Claim, ClaimSource, Concept, Craft, Source, User
from app.retrieval.stamps import current_embedding_model

from ..craft_fixtures import unit
from .test_retrieval_stamps_db import route_to

__all__ = [
    "ASKERS",
    "CRAFT",
    "EAST",
    "FAILED",
    "NEAR",
    "NORTH",
    "NOW",
    "OTHER_CRAFT",
    "QELMORANT",
    "RESEARCHER",
    "SITE",
    "SLUG",
    "SOURCE",
    "Question",
    "asked",
    "fact",
    "seeded_session",
]

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
SITE = "https://kalavigyan.example"
SLUG = "Qelmor-Print"
MODEL = "answer-gap-test-embedder"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-answer-gaps/{name}")


CRAFT, OTHER_CRAFT, QELMORANT, SOURCE, FAILED = (
    key(name) for name in ("craft", "other-craft", "qelmorant", "source", "failed")
)
ASKERS = tuple(key(f"asker-{n}") for n in range(3))
RESEARCHER = key("researcher")
EAST = unit(1.0)
NEAR = unit(0.96, 0.28)
NORTH = unit(0.0, 1.0)


@dataclass(frozen=True)
class Question:
    text: str
    asker: uuid.UUID | None
    days_ago: float
    vector: list[float] = field(default_factory=lambda: EAST)
    verdict: str = "THIN"
    lacking: tuple[str, ...] = ("CHEMISTRY",)
    lacks: tuple[str, ...] = ("FEW_SENTENCES",)
    craft: uuid.UUID = CRAFT


async def seeded_session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await route_to(session, MODEL)
            await _seed(session)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def asked(session: AsyncSession, question: Question) -> uuid.UUID:
    answer = uuid.uuid4()
    session.add(
        Answer(
            id=answer,
            userId=question.asker,
            question=question.text,
            mode="HYBRID",
            craftId=question.craft,
            createdAt=NOW - timedelta(days=question.days_ago),
        )
    )
    await session.flush()
    session.add(
        AnswerVerdict(
            answerId=answer,
            craftId=question.craft,
            verdict=question.verdict,
            fields=list(question.lacking),
            lacking=[] if question.verdict == "ANSWERED" else list(question.lacking),
            lacks=[] if question.verdict == "ANSWERED" else list(question.lacks),
            sentences=0 if question.verdict == "UNANSWERED" else 2,
            embedding=question.vector,
            embeddingModel=current_embedding_model(),
        )
    )
    await session.flush()
    return answer


async def fact(
    session: AsyncSession, text: str, field_name: str, vector: Sequence[float] = EAST
) -> uuid.UUID:
    claim = uuid.uuid4()
    session.add(
        Claim(
            id=claim,
            subjectType="CONCEPT",
            subjectId=QELMORANT,
            predicate="states",
            text=text,
            evidenceLevel="PROVISIONAL",
            origin="IMPORT",
            field=field_name,
            embedding=list(vector),
        )
    )
    await session.flush()
    session.add(ClaimSource(claimId=claim, sourceId=SOURCE, quote=text, locator="p. 2"))
    await session.flush()
    return claim


async def _seed(session: AsyncSession) -> None:
    session.add_all(
        [
            Craft(id=CRAFT, slug=SLUG, name="Qelmor Print"),
            Craft(id=OTHER_CRAFT, slug="Qelmor-Weave", name="Qelmor Weave"),
            *(
                User(id=user, name=name, email=f"{name.split()[0].lower()}.asker@example.org", role="STUDENT")
                for user, name in zip(ASKERS, ("Priya Asker", "Farhan Asker", "Meera Asker"), strict=True)
            ),
            User(id=RESEARCHER, name="Gap Researcher", email="gap.researcher@example.org", role="RESEARCHER"),
            Source(id=SOURCE, kind="BOOK", title="Qelmor dyeing"),
        ]
    )
    await session.flush()
    session.add(Concept(id=QELMORANT, craftId=CRAFT, type="MATERIAL", name="Qelmorant"))
    await session.flush()
    session.add(
        Claim(
            id=FAILED,
            subjectType="CONCEPT",
            subjectId=QELMORANT,
            predicate="states",
            text="A qelmor pattern note that lost its source.",
            evidenceLevel="PROVISIONAL",
            origin="IMPORT",
            field="DESIGN",
        )
    )
    await session.flush()
    session.add(
        ClaimSource(claimId=FAILED, sourceId=SOURCE, quote="a quote no longer found", quoteCheck="FAIL")
    )
    await session.flush()
