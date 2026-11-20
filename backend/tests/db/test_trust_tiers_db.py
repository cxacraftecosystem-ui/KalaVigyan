import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Refused
from app.models import AuditLog, Claim, ReviewEvent, User
from app.research.review_switch import ReviewSwitchUpdate
from app.research.trust_tiers import TierUpdate, drawn_for_review
from app.services import app_settings, trust_tiers
from app.services.fact_proposals import propose_fact_run
from app.services.task_reservations import claim_task, claim_tasks

from .contribution_seed import CONCEPT, NOW, adapters, fact, person, seeded_session
from .open_work_seed import RESEARCHER, SITE, SLUG, opened_session

pytestmark = pytest.mark.db

PREFIX = f"craft:{SLUG}"
OPEN_KEYS = [
    f"MISSING_FIELD:{PREFIX}:{field}"
    for field in ("OVERVIEW", "PROCESS", "PHYSICS", "MATERIALS", "GEOGRAPHY", "GEOLOGY", "CLIMATE", "ECOLOGY")
] + [f"MISSING_FIELD:{PREFIX}:{field}" for field in ("BOTANY", "ECONOMICS", "DESIGN", "HEALTH")]


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


@pytest.fixture
async def work_session() -> AsyncIterator[AsyncSession]:
    async for opened in opened_session():
        yield opened


def proposed(user: User, status: str, number: int) -> Claim:
    return Claim(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"test-trust-tiers/{user.id}/{number}"),
        subjectType="CONCEPT",
        subjectId=CONCEPT,
        predicate="states",
        text=f"Contributed fact number {number} about the queue test craft.",
        evidenceLevel="PROVISIONAL",
        origin="CONTRIBUTION",
        status=status,
        createdById=user.id,
    )


async def recorded(session: AsyncSession, user: User, statuses: list[str]) -> None:
    session.add_all([proposed(user, status, number) for number, status in enumerate(statuses)])
    await session.flush()


async def test_an_account_s_tier_is_read_from_its_accepted_refused_and_waiting_facts(
    session: AsyncSession,
) -> None:
    researcher = await person(session, "RESEARCHER")
    await recorded(
        session, researcher, ["APPROVED"] * 4 + ["IN_REVIEW"] * 2 + ["REJECTED"] * 2 + ["DRAFT"] * 3
    )
    standing = await trust_tiers.account_standing(session, researcher.id)
    assert (standing.accepted, standing.refused, standing.waiting) == (6, 2, 3)
    assert (standing.tier, standing.earned, standing.tasks_held_max, standing.facts_per_hour) == (
        "ESTABLISHED",
        "ESTABLISHED",
        10,
        60,
    )
    assert (standing.review_sample_percent, standing.override) == (100, None)


async def test_an_admin_holds_an_account_at_a_tier_and_gives_it_back_to_its_record(
    session: AsyncSession,
) -> None:
    researcher = await person(session, "RESEARCHER")
    admin = await person(session, "ADMIN")
    held = await trust_tiers.set_tier(
        session, admin, researcher.id, TierUpdate(tier="PROVEN", note="Known to the centre."), now=NOW
    )
    assert (held.tier, held.earned, held.tasks_held_max, held.review_sample_percent) == (
        "PROVEN",
        "NEW",
        20,
        20,
    )
    assert held.override is not None and (held.override.note, held.override.set_by) == (
        "Known to the centre.",
        admin.id,
    )
    (audit,) = await session.scalars(select(AuditLog).where(AuditLog.action == "knowledge.trust_tier_set"))
    assert (audit.actorId, audit.detail) == (admin.id, {"tier": "PROVEN", "note": "Known to the centre."})
    back = await trust_tiers.set_tier(session, admin, researcher.id, TierUpdate(tier=None), now=NOW)
    assert (back.tier, back.override) == ("NEW", None)


async def test_admins_see_every_contributor_s_standing_most_accepted_first(session: AsyncSession) -> None:
    steady = await person(session, "RESEARCHER")
    starting = await person(session, "RESEARCHER")
    professor = await person(session, "PROFESSOR")
    await recorded(session, steady, ["APPROVED"] * 5)
    await recorded(session, starting, ["REJECTED"])
    await trust_tiers.set_tier(session, professor, professor.id, TierUpdate(tier="NEW"), now=NOW)
    listed = (await trust_tiers.trust_standings(session, limit=200)).accounts
    mine = [item for item in listed if item.user_id in {steady.id, starting.id, professor.id}]
    assert [(item.user_id, item.tier) for item in mine] == [
        (steady.id, "ESTABLISHED"),
        (professor.id, "NEW"),
        (starting.id, "NEW"),
    ]
    assert next(item for item in mine if item.user_id == professor.id).tasks_held_max == 20


async def test_the_tasks_one_account_holds_at_once_follow_its_tier(work_session: AsyncSession) -> None:
    admin = User(
        id=uuid.uuid4(), name="Tier Admin", email=f"{uuid.uuid4().hex[:12]}@example.org", role="ADMIN"
    )
    work_session.add(admin)
    await work_session.flush()
    await trust_tiers.set_tier(work_session, admin, RESEARCHER, TierUpdate(tier="ESTABLISHED"), now=NOW)
    for key in OPEN_KEYS[:10]:
        await claim_task(work_session, RESEARCHER, key, site=SITE, now=NOW)
    with pytest.raises(Refused, match=r"holds 10 tasks.*\(established\)"):
        await claim_task(work_session, RESEARCHER, OPEN_KEYS[10], site=SITE, now=NOW)


async def test_several_tasks_are_claimed_each_on_its_own(work_session: AsyncSession) -> None:
    keys = [OPEN_KEYS[0], f"MISSING_FIELD:{PREFIX}:HISTORY", OPEN_KEYS[1]]
    claims = await claim_tasks(work_session, RESEARCHER, keys, site=SITE, now=NOW)
    assert [hold.task_key for hold in claims.held] == [OPEN_KEYS[0], OPEN_KEYS[1]]
    assert [refusal.task_key for refusal in claims.refused] == [keys[1]]
    assert "No open task" in claims.refused[0].problem
    assert (claims.tier, claims.holding, claims.holding_max) == ("NEW", 2, 5)


async def test_a_new_contributor_waits_for_review_even_with_the_switch_on_auto(session: AsyncSession) -> None:
    researcher = await person(session, "RESEARCHER")
    admin = await person(session, "ADMIN")
    await app_settings.set_review_switch(session, ReviewSwitchUpdate(agent="AUTO"), admin.id)
    ran = await propose_fact_run(
        session, fact(), researcher, "AGENT", adapters=adapters(), now=NOW, ticket=uuid.uuid4()
    )
    reply = ran.reply
    assert (reply.outcome, reply.status, reply.in_review_queue) == ("WAITING", "DRAFT", True)
    assert reply.message.endswith("as a new contributor's facts do.")
    (event,) = await session.scalars(select(ReviewEvent).where(ReviewEvent.claimId == reply.claim_id))
    assert (
        event.note
        == "AGENT proposal waits hidden for a Professor's or Admin's approval: a new contributor's fact"
    )


@pytest.mark.parametrize(
    ("drawn", "status", "queued"), [(False, "APPROVED", False), (True, "IN_REVIEW", True)]
)
async def test_a_proven_contributor_publishes_at_once_and_a_drawn_share_enters_the_review_queue(
    session: AsyncSession, drawn: bool, status: str, queued: bool
) -> None:
    researcher = await person(session, "RESEARCHER")
    admin = await person(session, "ADMIN")
    await trust_tiers.set_tier(session, admin, researcher.id, TierUpdate(tier="PROVEN"), now=NOW)
    tokens = (uuid.uuid5(uuid.NAMESPACE_URL, f"draw/{number}") for number in range(200))
    ticket = next(token for token in tokens if drawn_for_review(token) is drawn)
    ran = await propose_fact_run(
        session, fact(), researcher, "AGENT", adapters=adapters(), now=NOW, ticket=ticket
    )
    reply = ran.reply
    assert (reply.outcome, reply.status, reply.in_review_queue, reply.approved_at_once) == (
        "PUBLISHED",
        status,
        queued,
        not drawn,
    )
    claim = await session.get(Claim, reply.claim_id)
    assert claim is not None and (claim.status, claim.evidenceLevel) == (status, "PROVISIONAL")
