import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import (
    Claim,
    ClaimSource,
    Concept,
    Craft,
    ImageContribution,
    Process,
    ProcessStage,
    Source,
    UploadLink,
    User,
)
from app.research.upload_links import SlotDeclaration, UploadSlot
from app.services import upload_links as links

from ..pictures import FakeObjects, picture, screen_tools
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 19, 12, tzinfo=UTC)
SLUG = "Upload-Link-Test-Craft"
CRAFT = uuid.UUID("2b7f0000-0000-4000-8000-000000000001")
CONCEPT = uuid.UUID("2b7f0000-0000-4000-8000-000000000002")
SOURCE = uuid.UUID("2b7f0000-0000-4000-8000-000000000003")
FACT = uuid.UUID("2b7f0000-0000-4000-8000-000000000004")
PROCESS = uuid.UUID("2b7f0000-0000-4000-8000-000000000005")
STAGE = uuid.UUID("2b7f0000-0000-4000-8000-000000000006")
PHOTO = {
    "origin": "PHOTOGRAPH",
    "caption": "The vat turns yellow-green",
    "altText": "A clay vat of yellow-green liquid",
    "rightsConfirmed": True,
    "termsVersion": "2026-11-19",
}


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        opened.add(Craft(id=CRAFT, name="Upload Link Test Craft", slug=SLUG))
        opened.add(Source(id=SOURCE, kind="PAPER", title="Indigo vats", licence="CC-BY-4.0", year=2020))
        await opened.flush()
        opened.add(Concept(id=CONCEPT, craftId=CRAFT, type="MATERIAL", name="Indigo"))
        opened.add(Process(id=PROCESS, craftId=CRAFT, name="Dyeing"))
        await opened.flush()
        opened.add(ProcessStage(id=STAGE, processId=PROCESS, ordinal=1, name="Reducing the vat"))
        opened.add(_fact())
        await opened.flush()
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


@pytest.fixture
async def owner(session: AsyncSession) -> User:
    return await _person(session)


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


async def _person(session: AsyncSession, role: str = "RESEARCHER") -> User:
    key = uuid.uuid4()
    user = User(id=key, name=f"{role.title()} {key.hex[:4]}", email=f"{key.hex[:12]}@example.org", role=role)
    session.add(user)
    await session.flush()
    return user


def _slot(**changes: Any) -> UploadSlot:
    return UploadSlot.model_validate(
        {"craftSlug": SLUG, "stageId": str(STAGE), "claimIds": [str(FACT)]} | changes
    )


def _picture(seed: int = 1) -> links.Picture:
    return links.Picture(declaration=SlotDeclaration.model_validate(PHOTO), data=picture(seed=seed))


def _filling(now: datetime = NOW) -> links.Filling:
    return links.Filling(objects=cast(Any, FakeObjects()), tools=screen_tools(), now=now)


async def _row(session: AsyncSession, token: str) -> UploadLink:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    found = await session.scalar(select(UploadLink).where(UploadLink.linkHash == digest))
    assert found is not None
    return found


async def test_a_link_takes_one_picture_for_its_craft_stage_and_fact(
    session: AsyncSession, owner: User
) -> None:
    issued = await links.start_upload(session, owner, _slot(), None, now=NOW)
    assert (issued.stage is not None and issued.stage.name, [fact.id for fact in issued.facts]) == (
        "Reducing the vat",
        [FACT],
    )
    filling = _filling()
    made = await links.fill_by_link(session, owner, issued.link_token, _picture(), filling=filling)
    assert (made.craftId, made.stageId, made.claimIds, made.status) == (CRAFT, STAGE, [FACT], "PENDING")
    with pytest.raises(links.LinkGone, match="used already"):
        await links.fill_by_link(session, owner, issued.link_token, _picture(2), filling=filling)
    view = await links.link_view(session, owner, issued.link_token, now=NOW)
    assert (view.state, view.contribution_id) == ("USED", made.id)
    row = await _row(session, issued.link_token)
    assert issued.link_token not in (row.linkHash, row.slotHash)


async def test_an_expired_link_refuses_and_is_renewed_for_the_same_slot(
    session: AsyncSession, owner: User
) -> None:
    issued = await links.start_upload(session, owner, _slot(), None, now=NOW)
    later = NOW + timedelta(minutes=30)
    with pytest.raises(links.LinkGone, match="expired"):
        await links.fill_by_link(session, owner, issued.link_token, _picture(), filling=_filling(now=later))
    assert (await links.link_view(session, owner, issued.link_token, now=later)).state == "EXPIRED"
    renewed = await links.renew_link(session, owner, issued.link_token, now=later)
    fresh = await _row(session, renewed.link_token)
    assert (fresh.craftId, fresh.stageId, fresh.claimIds, fresh.expiresAt) == (
        CRAFT,
        STAGE,
        [FACT],
        later + timedelta(minutes=30),
    )


async def test_another_person_can_neither_read_nor_use_the_link(session: AsyncSession, owner: User) -> None:
    stranger = await _person(session)
    issued = await links.start_upload(session, owner, _slot(), None, now=NOW)
    with pytest.raises(links.UnknownLink):
        await links.link_view(session, stranger, issued.link_token, now=NOW)
    with pytest.raises(links.UnknownLink):
        await links.fill_by_link(session, stranger, issued.link_token, _picture(), filling=_filling())


async def test_a_link_names_a_shown_fact_and_a_stage_of_its_own_craft(
    session: AsyncSession, owner: User
) -> None:
    with pytest.raises(InvalidInput, match="No shown fact"):
        await links.start_upload(session, owner, _slot(claimIds=[str(uuid.uuid4())]), None, now=NOW)
    with pytest.raises(InvalidInput, match="stage"):
        await links.start_upload(session, owner, _slot(stageId=str(uuid.uuid4())), None, now=NOW)
    with pytest.raises(InvalidInput, match="No craft"):
        await links.start_upload(session, owner, _slot(craftSlug="No-Such-Craft"), None, now=NOW)


async def test_a_declared_slot_takes_the_bytes_once_without_a_session(
    session: AsyncSession, owner: User
) -> None:
    declaration = SlotDeclaration.model_validate(PHOTO)
    issued = await links.start_upload(session, owner, _slot(), declaration, now=NOW)
    assert issued.slot_token is not None
    filling = _filling()
    made = await links.fill_slot(session, issued.slot_token, picture(), filling=filling)
    stored = await session.get(ImageContribution, made.id)
    assert stored is not None and (stored.contributorId, stored.caption) == (owner.id, PHOTO["caption"])
    with pytest.raises(links.LinkGone, match="used already"):
        await links.fill_slot(session, issued.slot_token, picture(seed=2), filling=filling)
    with pytest.raises(links.LinkGone, match="used already"):
        await links.fill_by_link(session, owner, issued.link_token, _picture(3), filling=filling)


async def test_a_person_holds_at_most_ten_open_links(session: AsyncSession, owner: User) -> None:
    for _ in range(10):
        await links.start_upload(session, owner, _slot(), None, now=NOW)
    with pytest.raises(InvalidInput, match="10 open upload links"):
        await links.start_upload(session, owner, _slot(), None, now=NOW)
    assert (await links.start_upload(session, owner, _slot(), None, now=NOW + timedelta(minutes=31))).facts
