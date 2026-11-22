import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_engine
from app.models import (
    AccessRoster,
    Answer,
    Claim,
    ClaimSource,
    Concept,
    Craft,
    SavedItem,
    Source,
    User,
    UserPreference,
)
from app.research.explainer import Explainer
from app.research.vocabulary import CONCEPT_TYPE_DISCIPLINES
from app.services.explainer_payload import FIRST_VERSION, stored_payload

from ..contracts.explainer_golden import DOCUMENT, golden_json

__all__ = [
    "NOW",
    "Seeded",
    "claim_of",
    "craft_row",
    "first_answer",
    "reader",
    "saved_row",
    "seeded",
]

NOW = datetime.now(UTC).replace(microsecond=0)


@dataclass(frozen=True)
class Seeded:
    sessions: async_sessionmaker[AsyncSession]
    session: AsyncSession


@asynccontextmanager
async def seeded() -> AsyncIterator[Seeded]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            factory = async_sessionmaker(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )
            async with factory() as session:
                yield Seeded(factory, session)
        finally:
            await transaction.rollback()


async def reader(session: AsyncSession, *, digest: bool = False) -> User:
    email = f"alerts-{uuid.uuid4().hex[:10]}@example.com"
    user = User(id=uuid.uuid4(), name="Alerts Reader", email=email, role="STUDENT")
    session.add(user)
    await session.flush()
    session.add_all(
        [AccessRoster(email=email, status="ACTIVE"), UserPreference(userId=user.id, alertDigest=digest)]
    )
    await session.commit()
    return user


async def craft_row(session: AsyncSession) -> Craft:
    craft = Craft(id=uuid.uuid4(), slug=f"Alerts-Test-{uuid.uuid4().hex[:8]}", name="Alerts Test Print")
    session.add(craft)
    await session.commit()
    return craft


async def first_answer(
    session: AsyncSession, user: User, craft: Craft | None = None, *, claim_ids: tuple[uuid.UUID, ...] = ()
) -> Explainer:
    explainer = Explainer.model_validate(golden_json(DOCUMENT) | {"answerId": str(uuid.uuid4())})
    session.add(
        Answer(
            id=explainer.answer_id,
            userId=user.id,
            question=explainer.question,
            mode="DEEP",
            craftId=craft.id if craft else None,
            payload=stored_payload(explainer, None),
            claimIds=list(claim_ids),
            explainerId=explainer.answer_id,
            explainerVersion=FIRST_VERSION,
        )
    )
    await session.commit()
    return explainer


async def saved_row(
    session: AsyncSession, user: User, explainer_id: uuid.UUID, *, checked_at: datetime | None
) -> None:
    session.add(SavedItem(userId=user.id, answerId=explainer_id, seenVersion=1, checkedAt=checked_at))
    await session.commit()


async def claim_of(
    session: AsyncSession,
    craft: Craft,
    concept_type: str,
    *,
    created_at: datetime,
    level: str = "PROVISIONAL",
    filed: tuple[str, ...] | None = None,
) -> uuid.UUID:
    concept = Concept(id=uuid.uuid4(), craftId=craft.id, type=concept_type, name=f"{concept_type} finding")
    source = Source(id=uuid.uuid4(), kind="PAPER", title=f"A paper on {concept_type.lower()}")
    session.add_all([concept, source])
    await session.flush()
    field, fields = _filed(concept_type, filed)
    claim = Claim(
        id=uuid.uuid4(),
        subjectType="CONCEPT",
        subjectId=concept.id,
        predicate="states",
        text=f"A cited {concept_type.lower()} finding.",
        evidenceLevel=level,
        origin="IMPORT",
        field=field,
        fields=fields,
        createdAt=created_at,
    )
    session.add(claim)
    await session.flush()
    session.add(ClaimSource(claimId=claim.id, sourceId=source.id, quote="A cited finding."))
    await session.commit()
    return claim.id


def _filed(concept_type: str, filed: tuple[str, ...] | None) -> tuple[str | None, list[str]]:
    if filed is None:
        return CONCEPT_TYPE_DISCIPLINES.get(concept_type), []
    return (filed[0], list(filed[1:])) if filed else (None, [])
