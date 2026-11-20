import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import CraftCategory, PageDraft, User
from app.research.page_drafts import DRAFT_LIFETIME, DraftAddition
from app.research.page_proposals import PageProposalResult, PageSubject
from app.research.supplied_sources import SupplySource
from app.services import page_drafts, supplied_sources
from app.services.supplied_sources_identity import no_lookup

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 21, 9, tzinfo=UTC)
FIRST, SECOND = "draft-test-first", "draft-test-second"
FACT = {
    "subject": {"kind": "category", "slug": FIRST},
    "field": "HISTORY",
    "statement": "Block printing on cotton was traded from these ports by the sixteenth century.",
    "sources": [
        {
            "url": "https://example.org/trade",
            "title": "Trade",
            "quotes": [{"text": "traded from these ports"}],
        }
    ],
}


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        for order, slug in enumerate((FIRST, SECOND), start=980):
            opened.add(
                CraftCategory(id=uuid.uuid4(), slug=slug, name=slug.replace("-", " "), sortOrder=order)
            )
        await opened.flush()
        yield opened


async def person(session: AsyncSession, role: str = "RESEARCHER") -> User:
    token = uuid.uuid4()
    user = User(
        id=token, name=f"{role.title()} {token.hex[:4]}", email=f"{token.hex[:12]}@example.org", role=role
    )
    session.add(user)
    await session.flush()
    return user


def subject(slug: str = FIRST) -> PageSubject:
    return PageSubject(kind="category", slug=slug)


def adding(**parts: Any) -> DraftAddition:
    return DraftAddition.model_validate(parts)


async def test_one_open_draft_per_account_and_page(session: AsyncSession) -> None:
    owner = await person(session)
    first = await page_drafts.create_draft(session, owner, subject(), now=NOW)
    again = await page_drafts.create_draft(session, owner, subject(), now=NOW)
    other = await page_drafts.create_draft(session, owner, subject(SECOND), now=NOW)
    theirs = await page_drafts.create_draft(session, await person(session), subject(), now=NOW)
    assert first.id == again.id and len({first.id, other.id, theirs.id}) == 3
    assert (first.state, first.version, first.expiresAt) == ("OPEN", 1, NOW + DRAFT_LIFETIME)


async def test_an_unknown_page_and_too_many_open_drafts_are_refused(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await person(session)
    with pytest.raises(InvalidInput, match="No category has the slug"):
        await page_drafts.create_draft(session, owner, subject("draft-test-missing"), now=NOW)
    monkeypatch.setattr(page_drafts, "DRAFTS_OPEN_MAX", 1)
    await page_drafts.create_draft(session, owner, subject(), now=NOW)
    with pytest.raises(InvalidInput, match="1 open drafts"):
        await page_drafts.create_draft(session, owner, subject(SECOND), now=NOW)


async def test_parts_are_kept_changed_and_counted_with_each_version(session: AsyncSession) -> None:
    owner = await person(session)
    draft = await page_drafts.create_draft(session, owner, subject(), now=NOW)
    later = NOW + timedelta(hours=2)
    added = await page_drafts.add_to_draft(
        session, owner, draft.id, adding(facts=[FACT], note="Trade first."), now=later
    )
    assert (added.version, added.expiresAt, added.bytes > 0) == (2, later + DRAFT_LIFETIME, True)
    held = page_drafts.held_parts(added)
    assert (len(held.facts), held.note) == (1, "Trade first.")
    removed = await page_drafts.remove_from_draft(session, owner, draft.id, ("fact", 0), now=later)
    assert (removed.version, page_drafts.held_parts(removed).facts) == (3, [])
    view = page_drafts.draft_view(removed, message="m", next_step="n", full=True)
    assert view.draft is not None and view.counts.facts == 0 and view.parts == []


async def test_another_account_s_or_an_expired_draft_is_not_found(session: AsyncSession) -> None:
    owner = await person(session)
    draft = await page_drafts.create_draft(session, owner, subject(), now=NOW)
    with pytest.raises(InvalidInput, match="No open draft of yours"):
        await page_drafts.own_draft(session, await person(session), draft.id, now=NOW)
    with pytest.raises(InvalidInput, match="No open draft of yours"):
        await page_drafts.own_draft(session, owner, draft.id, now=NOW + DRAFT_LIFETIME)
    fresh = await page_drafts.create_draft(session, owner, subject(), now=NOW + DRAFT_LIFETIME)
    assert fresh.id != draft.id and await session.get(PageDraft, draft.id) is None


async def test_a_draft_holds_at_most_its_size_and_only_its_own_sources(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await person(session)
    draft = await page_drafts.create_draft(session, owner, subject(), now=NOW)
    supplied = await supplied_sources.supply_source(
        session, await person(session), supplied_draft(), lookup=no_lookup, now=NOW
    )
    with pytest.raises(InvalidInput, match="not this account's"):
        await page_drafts.add_to_draft(
            session, owner, draft.id, adding(supplied_sources=[supplied.row.id]), now=NOW
        )
    monkeypatch.setattr(page_drafts, "DRAFT_BYTES_MAX", 100)
    with pytest.raises(InvalidInput, match="more than the 100"):
        await page_drafts.add_to_draft(session, owner, draft.id, adding(facts=[FACT]), now=NOW)


async def test_a_submitted_draft_is_read_but_never_changed(session: AsyncSession) -> None:
    owner = await person(session)
    draft = await page_drafts.create_draft(session, owner, subject(), now=NOW)
    await page_drafts.add_to_draft(session, owner, draft.id, adding(facts=[FACT]), now=NOW)
    result = PageProposalResult(
        subject=subject(),
        page_url="https://kalavigyan.example/categories/x",
        accepted=1,
        refused=0,
        parts=[],
        message="1.",
    )
    await page_drafts.record_submission(session, draft, result, now=NOW)
    with pytest.raises(InvalidInput, match="was submitted"):
        await page_drafts.add_to_draft(session, owner, draft.id, adding(note="Too late."), now=NOW)
    read = await page_drafts.own_draft(session, owner, draft.id, now=NOW, open_only=False)
    assert (
        read.state == "SUBMITTED"
        and page_drafts.draft_view(read, message="m", next_step="n").result == result
    )
    assert len(page_drafts.bundle_of(read).facts) == 1


def supplied_draft() -> SupplySource:
    return SupplySource.model_validate(
        {
            "identity": {"url": "https://archive.example.org/trade", "title": "Ports and cloth"},
            "access": {"how": "ARCHIVE", "accessedOn": "2026-11-20"},
            "passages": [{"text": "Cloth was traded from these ports for centuries.", "locator": "folio 3"}],
        }
    )
