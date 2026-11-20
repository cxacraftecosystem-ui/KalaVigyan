import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ImageContribution, MediaAsset
from app.services.monograph_generated import generated_document

from .page_documents_seed import CRAFT, CRAFT_CLAIM, CRAFT_SLUG, NOW, PICTURE, seed
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-contributed-plates/{name}")


RECORD, FACTS, MASTHEAD, AI_UNSHOWN, WAITING = (
    key("record"),
    key("facts"),
    key("masthead"),
    key("ai-unshown"),
    key("waiting"),
)
UNSHOWN_FACT = key("unshown-fact")


def label(contribution_id: uuid.UUID) -> str:
    return f"{CRAFT_SLUG.lower()}/pictures/contributed-{contribution_id.hex[:12]}"


def picture(contribution_id: uuid.UUID, **values: Any) -> ImageContribution:
    defaults: dict[str, Any] = {
        "id": contribution_id,
        "craftId": CRAFT,
        "origin": "PHOTOGRAPH",
        "caption": f"The cloth after the alum bath ({contribution_id.hex[:4]})",
        "altText": "A length of printed cotton drying on a line",
        "termsVersion": "2026-11-19",
        "rightsConfirmedAt": NOW,
        "status": "APPROVED",
        "reviewedAt": NOW,
        "sha256": contribution_id.hex * 2,
        "assetId": key(f"asset-{contribution_id}"),
    }
    return ImageContribution(**(defaults | values))


def asset(contribution_id: uuid.UUID) -> MediaAsset:
    return MediaAsset(
        id=key(f"asset-{contribution_id}"),
        s3Key=f"media/contributed-plates/{contribution_id.hex}.webp",
        mime="image/webp",
        width=1200,
        height=900,
        visibility="CRAFT_SHARED",
    )


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await seed(opened)
        given = (RECORD, FACTS, MASTHEAD, AI_UNSHOWN, WAITING)
        opened.add_all([asset(each) for each in given])
        await opened.flush()
        opened.add_all(
            [
                picture(RECORD, slot="RECORD"),
                picture(FACTS, claimIds=[CRAFT_CLAIM]),
                picture(MASTHEAD, slot="MASTHEAD"),
                picture(
                    AI_UNSHOWN,
                    origin="AI_GENERATED",
                    generator="Imagen 4",
                    prompt="A block-printed cotton drying in the sun",
                    claimIds=[CRAFT_CLAIM, UNSHOWN_FACT],
                ),
                picture(WAITING, status="PENDING", reviewedAt=None),
            ]
        )
        await opened.flush()
        yield opened


async def test_approved_pictures_are_drawn_in_their_places_with_the_contributed_credit(
    session: AsyncSession,
) -> None:
    document = await generated_document(session, "craft", CRAFT_SLUG)
    assert document is not None
    chapters = {
        entry.label: entry.chapter for entry in document.content.components if entry.kind == "picture_plate"
    }
    assert chapters[label(RECORD)] == "market"
    assert chapters[label(FACTS)] == "chem"
    assert chapters[label(MASTHEAD)] == "glance"
    spec = document.specs[label(RECORD)]
    assert spec["picture"]["src"] == f"/api/crafts/contributed/{RECORD}"
    caption, credit = spec["figure"]["captions"][0]["unit"], spec["figure"]["credit"]
    assert document.content.units[caption].nodes == [f"The cloth after the alum bath ({RECORD.hex[:4]})"]
    assert document.content.units[credit].nodes == ["Contributed to KalaVigyan"]


async def test_the_curated_masthead_keeps_the_hero_and_no_waiting_or_unsupported_picture_is_drawn(
    session: AsyncSession,
) -> None:
    document = await generated_document(session, "craft", CRAFT_SLUG)
    assert document is not None
    assert document.content.layout[0].ref == PICTURE
    drawn = {entry.label for entry in document.content.components}
    assert label(WAITING) not in drawn and label(AI_UNSHOWN) not in drawn
