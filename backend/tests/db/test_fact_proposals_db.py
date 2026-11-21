import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import (
    AnswerGap,
    Claim,
    ClaimSource,
    Concept,
    Craft,
    CraftCategory,
    CraftSubCategory,
    ReviewEvent,
    Source,
    TaskReservation,
    User,
)
from app.research.knowledge_writes import FactProposal
from app.research.retrieval import EVERY_CHUNK_ACLS
from app.research.review_switch import ReviewSwitchUpdate
from app.research.trust_tiers import TierUpdate
from app.services import app_settings, trust_tiers
from app.services.candidate_writes import checks_of
from app.services.fact_proposals import ProposalAdapters, propose_fact
from app.services.knowledge_view import claims_for

from ..craft_fixtures import unit
from ..knowledge_writes.fakes import PAGE_URL, QUOTE, STATEMENT, FakeEmbedder, FakeFetcher, FakeJudge, page
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 19, 12, tzinfo=UTC)
SLUG = "Proposal-Gate-Test-Craft"
CATEGORY_SLUG = "proposal-gate-test-category"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-fact-proposals/{name}")


CATEGORY, FAMILY, CRAFT, CONCEPT, HELD = (
    key("category"),
    key("family"),
    key("craft"),
    key("concept"),
    key("held"),
)
HELD_TEXT = "Ajrakh printers resist the cloth with lime and gum arabic before dyeing."
CLOSE_REST = 0.4358898943540674
ADDS = {
    "verdicts": [{"candidate": "proposal", "adds": True, "coveredBy": [], "reason": "It counts the dips."}]
}


@dataclass(frozen=True)
class People:
    researcher: User
    professor: User


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        opened.add(
            CraftCategory(id=CATEGORY, slug=CATEGORY_SLUG, name="Proposal Gate Category", sortOrder=997)
        )
        await opened.flush()
        opened.add(
            CraftSubCategory(
                id=FAMILY, slug="proposal-gate-family", name="Gate", categoryId=CATEGORY, sortOrder=1
            )
        )
        await opened.flush()
        opened.add(Craft(id=CRAFT, slug=SLUG, name="Proposal Gate Test Craft", subCategoryId=FAMILY))
        await opened.flush()
        opened.add(Concept(id=CONCEPT, craftId=CRAFT, type="ARTISAN_ACTION", name="Proposal Gate Test Craft"))
        await opened.flush()
        opened.add(_held(HELD, HELD_TEXT, unit(0.0, 1.0)))
        await opened.flush()
        yield opened


@pytest.fixture
async def people(session: AsyncSession) -> People:
    made = People(_person("RESEARCHER"), _person("PROFESSOR"))
    session.add_all([made.researcher, made.professor])
    await session.flush()
    return made


def _person(role: str) -> User:
    token = uuid.uuid4()
    return User(
        id=token, name=f"{role.title()} {token.hex[:4]}", email=f"{token.hex[:12]}@example.org", role=role
    )


def _held(claim_id: uuid.UUID, text: str, vector: list[float]) -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=CONCEPT,
        predicate="states",
        text=text,
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
        field="PROCESS",
        embedding=vector,
    )


def proposal(statement: str = STATEMENT, quote: str = QUOTE, **changes: Any) -> FactProposal:
    body: dict[str, Any] = {
        "subject": {"kind": "craft", "slug": SLUG},
        "field": "PROCESS",
        "fields": ["CHEMISTRY"],
        "statement": statement,
        "sources": [
            {"url": PAGE_URL, "title": "Indigo in Ajrakh", "quotes": [{"text": quote, "locator": "para 2"}]}
        ],
    }
    return FactProposal.model_validate(body | changes)


def adapters(*replies: dict[str, Any], vector: list[float] | None = None) -> ProposalAdapters:
    return ProposalAdapters(
        fetcher=FakeFetcher({PAGE_URL: page()}),
        embed=FakeEmbedder(vector or unit(1.0)),
        judge=FakeJudge(*replies),
    )


async def proposed(session: AsyncSession, user: User, origin: str, gates: ProposalAdapters, **changes: Any):
    return await propose_fact(session, proposal(**changes), user, origin, adapters=gates, now=NOW)


async def held_at(session: AsyncSession, people: People, tier: str) -> None:
    update = TierUpdate(tier=tier, note="Held for the test.")
    await trust_tiers.set_tier(session, people.professor, people.researcher.id, update, now=NOW)


async def shown_ids(session: AsyncSession) -> set[uuid.UUID]:
    views, _ = await claims_for(
        session, await session.get(Craft, CRAFT), mode="HYBRID", acls=EVERY_CHUNK_ACLS
    )
    return {view.id for view in views}


async def test_a_contributor_s_fact_passes_every_gate_and_waits_hidden_by_default(
    session: AsyncSession, people: People
) -> None:
    reply = await proposed(session, people.researcher, "CONTRIBUTION", adapters(ADDS))
    assert (reply.outcome, reply.status, reply.level, reply.in_review_queue) == (
        "WAITING",
        "DRAFT",
        "PROVISIONAL",
        True,
    )
    claim = await session.get(Claim, reply.claim_id)
    assert (claim.subjectId, claim.origin, claim.createdById, claim.createdByKind) == (
        CONCEPT,
        "CONTRIBUTION",
        people.researcher.id,
        "USER",
    )
    assert (claim.field, claim.fields, claim.sourcesDiffer, claim.embedding is not None) == (
        "PROCESS",
        ["CHEMISTRY"],
        False,
        True,
    )
    checks = await checks_of(session, reply.claim_id)
    assert [(check.gate, check.passed) for check in checks] == [
        ("QUOTES", True),
        ("SOURCE", True),
        ("DUPLICATE", True),
        ("NOVELTY", True),
    ]
    assert (checks[3].reasons, checks[3].model, checks[3].checkedAt) == (
        ["It counts the dips."],
        "judge-model-1",
        NOW,
    )
    assert reply.claim_id not in await shown_ids(session)


async def test_the_quote_is_cited_from_a_contributed_source_with_its_locator(
    session: AsyncSession, people: People
) -> None:
    reply = await proposed(session, people.researcher, "CONTRIBUTION", adapters(ADDS))
    (cite,) = await session.scalars(select(ClaimSource).where(ClaimSource.claimId == reply.claim_id))
    assert (cite.quote, cite.locator, cite.quoteCheck, cite.relation, cite.foundBy) == (
        QUOTE,
        "para 2",
        "PASS",
        "DIRECT",
        "CONTRIBUTION",
    )
    source = await session.get(Source, cite.sourceId)
    assert (source.url, source.origin, source.addedById, source.reliability) == (
        PAGE_URL,
        "CONTRIBUTION",
        people.researcher.id,
        "C",
    )
    (event,) = await session.scalars(select(ReviewEvent).where(ReviewEvent.claimId == reply.claim_id))
    assert (event.actorKind, event.actorId, event.toStatus) == ("USER", people.researcher.id, "DRAFT")


async def test_with_the_switch_on_auto_an_established_contribution_goes_live_unreviewed(
    session: AsyncSession, people: People
) -> None:
    await app_settings.set_review_switch(
        session, ReviewSwitchUpdate(contribution="AUTO"), people.professor.id
    )
    await held_at(session, people, "ESTABLISHED")
    reply = await proposed(session, people.researcher, "CONTRIBUTION", adapters(ADDS))
    assert (reply.outcome, reply.status, reply.approved_at_once, reply.in_review_queue) == (
        "PUBLISHED",
        "IN_REVIEW",
        False,
        True,
    )
    assert reply.claim_id in await shown_ids(session)
    assert (await app_settings.review_switch(session)).stored()["AGENT"] == "APPROVAL"


async def test_a_professor_s_fact_is_approved_at_once_and_skips_the_queue(
    session: AsyncSession, people: People
) -> None:
    reply = await proposed(session, people.professor, "AGENT", adapters(ADDS))
    assert (reply.outcome, reply.status, reply.approved_at_once, reply.in_review_queue) == (
        "PUBLISHED",
        "APPROVED",
        True,
        False,
    )
    (event,) = await session.scalars(select(ReviewEvent).where(ReviewEvent.claimId == reply.claim_id))
    assert event.note == "AGENT proposal approved at once: proposed by a Professor account"


async def test_the_role_is_read_from_the_account_at_the_moment_of_the_write(
    session: AsyncSession, people: People
) -> None:
    stale = User(id=people.researcher.id, name="Stale", email="stale@example.org", role="PROFESSOR")
    waits = await proposed(session, stale, "CONTRIBUTION", adapters(ADDS))
    assert waits.outcome == "WAITING"
    people.researcher.role = "ADMIN"
    await session.flush()
    other = "Ajrakh printers dip the cloth in the indigo vat four times before washing it."
    gates = adapters(ADDS, vector=unit(0.0, 0.0, 1.0))
    approved = await proposed(session, people.researcher, "CONTRIBUTION", gates, statement=other)
    assert approved.outcome == "PUBLISHED" and approved.approved_at_once


async def test_a_quote_the_page_does_not_hold_is_refused_and_kept_only_for_audit(
    session: AsyncSession, people: People
) -> None:
    gates = adapters()
    reply = await proposed(
        session, people.professor, "CONTRIBUTION", gates, quote="The cloth is dipped nine times in a row"
    )
    assert (reply.outcome, reply.status, reply.level) == ("REFUSED", "REJECTED", "HYPOTHESIS")
    assert [(gate.gate, gate.passed) for gate in reply.gates] == [("QUOTES", False)]
    assert reply.message.startswith("Not added: the QUOTES gate refused it.")
    assert list(await session.scalars(select(ClaimSource).where(ClaimSource.claimId == reply.claim_id))) == []
    assert gates.embed.calls == [] and gates.judge.calls == []  # type: ignore[attr-defined]


async def test_a_held_fact_proposed_again_is_refused_as_a_duplicate(
    session: AsyncSession, people: People
) -> None:
    gates = adapters()
    held_quote = "resist the cloth with a paste of lime and gum arabic"
    reply = await proposed(
        session, people.researcher, "CONTRIBUTION", gates, statement=HELD_TEXT, quote=held_quote
    )
    assert (reply.outcome, reply.gates[-1].gate) == ("REFUSED", "DUPLICATE")
    (duplicate,) = [check for check in await checks_of(session, reply.claim_id) if check.gate == "DUPLICATE"]
    assert (duplicate.passed, duplicate.relatedClaimIds) == (False, [HELD])
    assert gates.judge.calls == []  # type: ignore[attr-defined]


async def test_a_fact_that_disagrees_is_published_as_sources_differ(
    session: AsyncSession, people: People
) -> None:
    near = key("near")
    session.add(_held(near, "Ajrakh cloth is dipped in the indigo vat twice.", unit(0.9, CLOSE_REST)))
    await session.flush()
    differs = {
        "candidate": "proposal",
        "held": str(near),
        "relation": "DIFFERS",
        "reason": "Two dips, not four.",
    }
    reply = await proposed(session, people.professor, "CONTRIBUTION", adapters({"comparisons": [differs]}))
    assert (reply.outcome, reply.sources_differ, reply.differs_from) == ("PUBLISHED", True, [near])
    assert (await session.get(Claim, near)).sourcesDiffer is True
    assert (await session.get(Claim, reply.claim_id)).sourcesDiffer is True
    assert [gate.gate for gate in reply.gates] == ["QUOTES", "SOURCE", "DUPLICATE", "NOVELTY"]


async def test_a_category_fact_is_filed_on_the_category_s_shared_concept(
    session: AsyncSession, people: People
) -> None:
    subject = {"kind": "category", "slug": CATEGORY_SLUG}
    reply = await proposed(session, people.professor, "CONTRIBUTION", adapters(), subject=subject)
    claim = await session.get(Claim, reply.claim_id)
    concept = await session.get(Concept, claim.subjectId)
    assert (concept.craftId, concept.subCategoryId, concept.name, concept.type) == (
        None,
        None,
        "Proposal Gate Category",
        "ARTISAN_ACTION",
    )
    assert reply.outcome == "PUBLISHED"


async def test_the_review_switch_is_stored_and_read_back(session: AsyncSession, people: People) -> None:
    assert (await app_settings.review_switch(session)).stored() == {
        "RESEARCH": "AUTO",
        "CONTRIBUTION": "APPROVAL",
        "AGENT": "APPROVAL",
    }
    await app_settings.set_review_switch(
        session, ReviewSwitchUpdate(research="APPROVAL"), people.professor.id
    )
    stored = (await app_settings.review_switch(session)).stored()
    assert stored == {"RESEARCH": "APPROVAL", "CONTRIBUTION": "APPROVAL", "AGENT": "APPROVAL"}


def held_task(user: User, task: str) -> TaskReservation:
    hour = timedelta(hours=1)
    return TaskReservation(taskKey=task, userId=user.id, reservedAt=NOW - hour, expiresAt=NOW + hour)


async def test_a_fact_that_passes_completes_the_task_its_proposer_claimed(
    session: AsyncSession, people: People
) -> None:
    task = f"THIN_FIELD:craft:{SLUG}:PROCESS"
    reservation = held_task(people.researcher, task)
    session.add(reservation)
    await session.flush()
    reply = await proposed(session, people.researcher, "AGENT", adapters(ADDS), taskKey=task)
    assert reply.outcome == "WAITING"
    assert (reservation.ending, reservation.endedAt) == ("COMPLETED", NOW)


async def test_a_refused_fact_gives_the_task_back_and_leaves_another_account_s_alone(
    session: AsyncSession, people: People
) -> None:
    mine, theirs = f"SECOND_SOURCE:craft:{SLUG}:PROCESS", f"THIN_FIELD:craft:{SLUG}:CHEMISTRY"
    held, other = held_task(people.researcher, mine), held_task(people.professor, theirs)
    session.add_all([held, other])
    await session.flush()
    refused = await proposed(
        session,
        people.researcher,
        "AGENT",
        adapters(),
        quote="The cloth is dipped nine times in a row",
        taskKey=mine,
    )
    assert refused.outcome == "REFUSED"
    assert (held.ending, held.endedAt) == ("RELEASED", NOW)
    passed = await proposed(session, people.researcher, "AGENT", adapters(ADDS), taskKey=theirs)
    assert passed.outcome == "WAITING" and (other.ending, other.endedAt) == (None, None)


async def test_a_fact_completes_the_question_task_whose_readers_lacked_one_of_its_fields(
    session: AsyncSession, people: People
) -> None:
    asked = {"question": "How many dips?", "fields": ["CHEMISTRY"], "firstAskedAt": NOW, "lastAskedAt": NOW}
    gap = AnswerGap(id=key("gap"), craftId=CRAFT, **asked)
    task, unknown = f"ANSWER_GAP:craft:{SLUG}:gap-{gap.id.hex}", f"ANSWER_GAP:craft:{SLUG}:gap-{key('x').hex}"
    reservation = held_task(people.researcher, task)
    session.add_all([gap, reservation])
    await session.flush()
    with pytest.raises(InvalidInput, match="asks about CHEMISTRY; the fact is filed under PROCESS"):
        await proposed(session, people.researcher, "AGENT", adapters(ADDS), taskKey=task, fields=[])
    with pytest.raises(InvalidInput, match="names no question readers asked"):
        await proposed(session, people.researcher, "AGENT", adapters(ADDS), taskKey=unknown)
    assert reservation.endedAt is None
    reply = await proposed(session, people.researcher, "AGENT", adapters(ADDS), taskKey=task)
    assert reply.outcome == "WAITING"
    assert (reservation.ending, reservation.endedAt) == ("COMPLETED", NOW)
