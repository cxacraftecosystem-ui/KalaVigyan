import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import AuditLog, Claim, OAuthGrant, OAuthToken, ReviewEvent, Source, StagedReviewItem, User
from app.research.review_queue import QueueApproval
from app.research.staged_reviews import ConfirmedItem, StagedConfirmation, StagedDecision
from app.services import review_queue_decisions as decisions, staged_reviews
from app.services.oauth_bearer import McpCaller
from app.services.review_queue_errors import DecisionConflict, NotYourQueue
from app.services.staged_review_confirm import confirm_batch, discard_batch
from app.services.staged_review_views import open_batches
from app.services.staged_reviews import stage_decisions

from .review_queue_seed import (
    ADMIN_OWN,
    AGENT_WAITING,
    LIVE,
    NOW,
    PUBLISHED,
    SLUG,
    SOURCE,
    People,
    seeded_session,
)
from .test_oauth_db import RESOURCE, registered

pytestmark = pytest.mark.db

WHY = "Both quotes say this of the vat, word for word."


@pytest.fixture
async def seeded() -> AsyncIterator[tuple[AsyncSession, People]]:
    async for opened in seeded_session():
        yield opened


async def caller_of(session: AsyncSession, user: User) -> McpCaller:
    client_id = uuid.UUID(await registered(session))
    grant = OAuthGrant(
        clientId=client_id,
        userId=user.id,
        scopes=["read", "review"],
        resource=RESOURCE,
        userTokenVersion=0,
        createdAt=NOW,
        expiresAt=NOW + timedelta(days=1),
    )
    session.add(grant)
    await session.flush()
    token = OAuthToken(
        grantId=grant.id,
        kind="ACCESS",
        tokenHash=uuid.uuid4().hex * 2,
        scopes=["read", "review"],
        expiresAt=NOW,
    )
    session.add(token)
    await session.flush()
    return McpCaller(user, frozenset({"read", "review"}), grant.id, token.id, "Claude")


def decided(kind: str, item: uuid.UUID, action: str, **more: object) -> StagedDecision:
    return StagedDecision.model_validate({"kind": kind, "id": item, "action": action, "reason": WHY, **more})


def asked() -> list[StagedDecision]:
    return [
        decided("FACTS", AGENT_WAITING, "approve"),
        decided("FACTS", LIVE, "reject"),
        decided("FACTS", ADMIN_OWN, "approve"),
        decided("FACTS", PUBLISHED, "approve"),
        decided(
            "SOURCES", SOURCE, "correct", source={"title": "Indigo vats and their chemistry", "year": 2007}
        ),
        decided("SOURCES_DIFFER", PUBLISHED, "clear"),
        decided("FACTS", AGENT_WAITING, "reject"),
    ]


async def item_rows(session: AsyncSession, batch_id: uuid.UUID) -> list[tuple[int, str, Any]]:
    found = await session.execute(
        select(StagedReviewItem.position, StagedReviewItem.state, StagedReviewItem.applied)
        .where(StagedReviewItem.batchId == batch_id)
        .order_by(StagedReviewItem.position)
    )
    return list(found.tuples().all())


async def audited(session: AsyncSession, action: str) -> set[tuple[uuid.UUID | None, str | None]]:
    rows = await session.scalars(select(AuditLog).where(AuditLog.action == action))
    return {(row.actorId, (row.detail or {}).get("client")) for row in rows.all()}


def as_confirmed(item: StagedReviewItem) -> ConfirmedItem:
    kept = {key: value for key, value in item.decision.items() if key not in ("kind", "id")}
    return ConfirmedItem.model_validate(kept | {"id": item.id})


async def statuses(session: AsyncSession) -> dict[uuid.UUID, str]:
    rows = await session.execute(select(Claim.id, Claim.status).where(Claim.id.in_([AGENT_WAITING, LIVE])))
    return {key: str(status) for key, status in rows.tuples().all()}


async def test_staging_checks_each_decision_by_the_review_rules_and_changes_nothing(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    before = await statuses(session)
    staged = await stage_decisions(session, asked(), await caller_of(session, people.admin), now=NOW)
    assert [(item.kind, item.itemId, item.action) for item in staged.items] == [
        ("FACTS", AGENT_WAITING, "approve"),
        ("FACTS", LIVE, "reject"),
        ("SOURCES", SOURCE, "correct"),
    ]
    refused = {each.index: each.reason for each in staged.refused}
    assert sorted(refused) == [2, 3, 5, 6]
    assert "own" in refused[2]
    assert "cannot be approved" in refused[3]
    assert "not marked" in refused[5]
    assert "earlier in the same call" in refused[6]
    assert staged.batch is not None and staged.batch.clientName == "Claude"
    assert staged.batch.expiresAt == NOW + timedelta(days=3) and staged.today == 3
    assert await statuses(session) == before
    assert await session.scalar(select(Source.title).where(Source.id == SOURCE)) == "Indigo vats"
    events = await session.scalars(select(ReviewEvent).where(ReviewEvent.claimId.in_([AGENT_WAITING, LIVE])))
    assert events.all() == []
    audits = await session.scalars(select(AuditLog.action).where(AuditLog.action.like("review.fact_%")))
    assert audits.all() == []


async def test_confirming_applies_the_chosen_items_through_the_review_decisions_and_names_the_client(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    staged = await stage_decisions(session, asked(), await caller_of(session, people.admin), now=NOW)
    first, second, _ = staged.items
    changed = "The quote holds after all, read with its page."
    chosen = StagedConfirmation(
        items=[
            ConfirmedItem(id=first.id, action="approve", reason=WHY),
            ConfirmedItem(id=second.id, action="approve", reason=changed),
        ]
    )
    assert staged.batch is not None
    confirmed = await confirm_batch(
        session, staged.batch.id, chosen, people.admin, now=NOW + timedelta(hours=1)
    )
    assert await statuses(session) == {AGENT_WAITING: "APPROVED", LIVE: "APPROVED"}
    assert SLUG in confirmed.owners.crafts and len(confirmed.decided) == 2
    rows = await item_rows(session, staged.batch.id)
    assert [(position, state) for position, state, _ in rows] == [
        (0, "APPLIED"),
        (1, "APPLIED"),
        (2, "SKIPPED"),
    ]
    assert rows[0][2] is None and rows[1][2]["action"] == "approve" and rows[1][2]["reason"] == changed
    assert (staged.batch.status, staged.batch.decidedById) == ("CONFIRMED", people.admin.id)
    assert await audited(session, "review.staged_applied") == {(people.admin.id, "Claude")}
    assert await audited(session, "review.fact_approved") == {(people.admin.id, None)}
    assert await session.scalar(select(Source.title).where(Source.id == SOURCE)) == "Indigo vats"


async def test_confirming_checks_each_item_again_and_refuses_one_decided_meanwhile(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    staged = await stage_decisions(session, asked()[:2], await caller_of(session, people.admin), now=NOW)
    first, second = staged.items
    seen = QueueApproval(note="Seen on the site.")
    await decisions.approve_item(session, decisions.ItemRef("FACTS", LIVE), people.professor, seen, now=NOW)
    chosen = StagedConfirmation(
        items=[ConfirmedItem(id=item.id, action=item.action, reason=WHY) for item in (first, second)]
    )
    assert staged.batch is not None
    await confirm_batch(session, staged.batch.id, chosen, people.admin, now=NOW)
    await session.refresh(second)
    await session.refresh(first)
    assert (first.state, second.state) == ("APPLIED", "REFUSED")
    assert second.outcome is not None and "cannot be rejected" in second.outcome


async def test_a_batch_expires_after_three_days_and_is_neither_listed_nor_confirmed(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    staged = await stage_decisions(session, asked()[:1], await caller_of(session, people.admin), now=NOW)
    assert staged.batch is not None
    listed = await open_batches(session, now=NOW + timedelta(days=2))
    assert [batch.id for batch in listed.batches] == [staged.batch.id]
    assert listed.batches[0].proposed_by == people.admin.name
    later = NOW + timedelta(days=3, minutes=1)
    assert (await open_batches(session, now=later)).batches == []
    chosen = StagedConfirmation(items=[ConfirmedItem(id=staged.items[0].id, action="approve", reason=WHY)])
    with pytest.raises(DecisionConflict):
        await confirm_batch(session, staged.batch.id, chosen, people.admin, now=later)
    assert (await statuses(session))[AGENT_WAITING] == "DRAFT"


async def test_only_an_admin_stages_or_confirms_and_a_discarded_batch_is_closed(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    with pytest.raises(NotYourQueue):
        await stage_decisions(session, asked()[:1], await caller_of(session, people.professor), now=NOW)
    staged = await stage_decisions(session, asked()[:1], await caller_of(session, people.admin), now=NOW)
    assert staged.batch is not None
    chosen = StagedConfirmation(items=[ConfirmedItem(id=staged.items[0].id, action="approve", reason=WHY)])
    with pytest.raises(NotYourQueue):
        await confirm_batch(session, staged.batch.id, chosen, people.professor, now=NOW)
    discarded = await discard_batch(session, staged.batch.id, people.admin, now=NOW)
    assert discarded.status == "DISCARDED"
    with pytest.raises(DecisionConflict):
        await confirm_batch(session, staged.batch.id, chosen, people.admin, now=NOW)


async def test_staging_stops_at_the_day_s_allowance(
    seeded: tuple[AsyncSession, People], monkeypatch: pytest.MonkeyPatch
) -> None:
    session, people = seeded
    caller = await caller_of(session, people.admin)
    await stage_decisions(session, asked()[:1], caller, now=NOW)
    assert await staged_reviews.staged_today(session, people.admin, now=NOW) == 1
    monkeypatch.setattr(
        staged_reviews,
        "day_allowance_problem",
        lambda today, count: None if today + count <= 2 else f"{today} and {count}",
    )
    with pytest.raises(InvalidInput, match="1 and 2"):
        await stage_decisions(session, asked()[1:2] + asked()[4:5], caller, now=NOW)


async def test_a_confirmed_source_correction_and_differ_clearing_reach_the_records_with_their_audits(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    published = await session.get(Claim, PUBLISHED)
    assert published is not None
    published.sourcesDiffer, published.differsOn = True, "the vat's colour"
    await session.flush()
    fixes = [asked()[4], decided("SOURCES_DIFFER", PUBLISHED, "clear")]
    staged = await stage_decisions(session, fixes, await caller_of(session, people.admin), now=NOW)
    assert staged.refused == [] and staged.batch is not None
    chosen = StagedConfirmation(items=[as_confirmed(item) for item in staged.items])
    await confirm_batch(session, staged.batch.id, chosen, people.admin, now=NOW)
    source = await session.get(Source, SOURCE, populate_existing=True)
    claim = await session.get(Claim, PUBLISHED, populate_existing=True)
    assert source is not None and (source.title, source.year) == ("Indigo vats and their chemistry", 2007)
    assert claim is not None and (claim.sourcesDiffer, claim.differsOn) == (False, None)
    actions = await session.scalars(
        select(AuditLog.action).where(
            AuditLog.action.in_(["source.retitled", "source.corrected", "review.sources_differ_cleared"])
        )
    )
    assert sorted(actions.all()) == ["review.sources_differ_cleared", "source.corrected", "source.retitled"]
