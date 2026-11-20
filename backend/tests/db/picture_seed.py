from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Claim,
    ClaimSource,
    Concept,
    Craft,
    ImageContribution,
    Material,
    Process,
    ProcessStage,
    Source,
    StageMaterial,
    User,
)
from app.research.image_contributions import IMAGE_TERMS_VERSION, ImageDeclaration
from app.services import image_contributions as images
from app.services.image_screens import ScreenTools

from ..pictures import FakeObjects, screen_tools
from .testimony_seed import rolled_back_session

__all__ = [
    "CRAFT",
    "FACT",
    "MATERIAL",
    "NOW",
    "SLUG",
    "STAGE",
    "People",
    "declaration",
    "people_in",
    "seeded_session",
    "sent",
]

NOW = datetime(2026, 11, 19, 12, tzinfo=UTC)
SLUG = "Image-Contribution-Test-Craft"
CRAFT = uuid.UUID("1a6e0000-0000-4000-8000-000000000001")
CONCEPT = uuid.UUID("1a6e0000-0000-4000-8000-000000000002")
SOURCE = uuid.UUID("1a6e0000-0000-4000-8000-000000000003")
FACT = uuid.UUID("1a6e0000-0000-4000-8000-000000000004")
PROCESS = uuid.UUID("1a6e0000-0000-4000-8000-000000000005")
STAGE = uuid.UUID("1a6e0000-0000-4000-8000-000000000006")
MATERIAL = uuid.UUID("1a6e0000-0000-4000-8000-000000000007")


@dataclass(frozen=True)
class People:
    researcher: User
    other_researcher: User
    professor: User
    admin: User


async def seeded_session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        opened.add(Craft(id=CRAFT, name="Image Contribution Test Craft", slug=SLUG))
        opened.add(Source(id=SOURCE, kind="PAPER", title="Indigo vats", licence="CC-BY-4.0", year=2020))
        await opened.flush()
        opened.add(Concept(id=CONCEPT, craftId=CRAFT, type="MATERIAL", name="Indigo"))
        opened.add(Process(id=PROCESS, craftId=CRAFT, name="Dyeing"))
        await opened.flush()
        opened.add(ProcessStage(id=STAGE, processId=PROCESS, ordinal=1, name="Reducing the vat"))
        opened.add(
            Material(id=MATERIAL, name="Test indigo cake", nameNorm="test indigo cake", conceptId=CONCEPT)
        )
        opened.add(_fact())
        await opened.flush()
        opened.add(StageMaterial(stageId=STAGE, materialId=MATERIAL))
        opened.add(
            ClaimSource(
                claimId=FACT,
                sourceId=SOURCE,
                quote="the reduced vat is yellow-green",
                locator="p. 4",
                quoteCheck="PASS",
                relation="DIRECT",
            )
        )
        await opened.flush()
        yield opened


async def people_in(session: AsyncSession) -> People:
    made = People(*(_person(role) for role in ("RESEARCHER", "RESEARCHER", "PROFESSOR", "ADMIN")))
    session.add_all([made.researcher, made.other_researcher, made.professor, made.admin])
    await session.flush()
    return made


def declaration(**changes: Any) -> ImageDeclaration:
    values: dict[str, Any] = {
        "craftSlug": SLUG,
        "claimIds": [str(FACT)],
        "origin": "AI_GENERATED",
        "generator": "ChatGPT, gpt-image-1",
        "prompt": "An indigo vat turning yellow-green as it is reduced",
        "caption": "The vat turns yellow-green as indigo is reduced",
        "altText": "A clay vat of yellow-green liquid with a blue film",
        "rightsConfirmed": True,
        "termsVersion": IMAGE_TERMS_VERSION,
    }
    return ImageDeclaration.model_validate(values | changes)


async def sent(
    session: AsyncSession, user: User, data: bytes, *, tools: ScreenTools | None = None, **changes: Any
) -> ImageContribution:
    row = await images.declare(session, user, declaration(**changes), now=NOW)
    upload = images.Upload(contribution_id=row.id, user=user, data=data)
    return await images.receive_file(
        session, upload, objects=cast(Any, FakeObjects()), tools=tools or screen_tools(), now=NOW
    )


def _fact() -> Claim:
    return Claim(
        id=FACT,
        subjectType="CONCEPT",
        subjectId=CONCEPT,
        predicate="states",
        text="A reduced indigo vat is yellow-green.",
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
        field="CHEMISTRY",
    )


def _person(role: str) -> User:
    key = uuid.uuid4()
    return User(id=key, name=f"{role.title()} {key.hex[:4]}", email=f"{key.hex[:12]}@example.org", role=role)
