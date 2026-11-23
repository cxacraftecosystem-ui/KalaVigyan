import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.research.review_queue import FactItem, ReviewFilters, ReviewQueuePage
from app.services.review_queue import QueueAdapters, list_review_queue
from app.services.review_queue_errors import UnknownCraft

from .review_queue_seed import (
    ADMIN_OWN,
    AGENT_WAITING,
    HELD,
    LIVE,
    NOW,
    PICTURE,
    PROPOSAL,
    RESEARCHED,
    SLUG,
    People,
    TurnsOf,
    seeded_session,
)
from .testimony_seed import seed as seed_testimony

pytestmark = pytest.mark.db

ADAPTERS = QueueAdapters(objects=None, turns_of=TurnsOf())
EVERY_PENDING = [AGENT_WAITING, PROPOSAL, LIVE, PICTURE, RESEARCHED]


@pytest.fixture
async def seeded() -> AsyncIterator[tuple[AsyncSession, People]]:
    async for opened in seeded_session():
        yield opened


async def listed(session: AsyncSession, viewer: User, **filters: Any) -> ReviewQueuePage:
    chosen = ReviewFilters(craft_slug=filters.pop("craft_slug", SLUG), **filters)
    return await list_review_queue(session, viewer, chosen, adapters=ADAPTERS, now=NOW)


def ids(page: ReviewQueuePage) -> list[uuid.UUID]:
    return [item.id for item in page.items]


async def test_an_admin_sees_every_pending_kind_from_other_people_newest_first(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    page = await listed(session, people.admin)
    assert ids(page) == EVERY_PENDING
    assert [item.kind for item in page.items] == ["FACTS", "COMPONENTS", "FACTS", "IMAGES", "FACTS"]
    assert page.kinds == [
        "FACTS",
        "TESTIMONY",
        "IMAGES",
        "COMPONENTS",
        "LAYOUTS",
        "STRUCTURE",
        "READINGS",
        "LAYERS",
        "STAGES",
    ]
    assert (page.counts, page.total, page.next_cursor) == (
        {
            "FACTS": 3,
            "TESTIMONY": 0,
            "IMAGES": 1,
            "COMPONENTS": 1,
            "LAYOUTS": 0,
            "STRUCTURE": 0,
            "READINGS": 0,
            "LAYERS": 0,
            "STAGES": 0,
        },
        5,
        None,
    )


async def test_only_an_admin_sees_who_proposed_and_research_has_no_proposer(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    shown = {item.id: item.proposer for item in (await listed(session, people.admin)).items}
    assert shown[AGENT_WAITING] is not None
    assert (shown[AGENT_WAITING].name, shown[AGENT_WAITING].role) == ("Meera Contributor", "RESEARCHER")
    assert shown[PICTURE] is not None and shown[PICTURE].name == "Meera Contributor"
    assert shown[RESEARCHED] is None
    hidden = await listed(session, people.professor)
    assert [item.proposer for item in hidden.items] == [None] * len(hidden.items)
    assert "Meera Contributor" not in hidden.model_dump_json()


async def test_a_professor_reviews_facts_testimony_and_structure_only_and_never_their_own(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    page = await listed(session, people.professor)
    assert page.kinds == ["FACTS", "TESTIMONY", "STRUCTURE", "READINGS", "STAGES"]
    assert ids(page) == [AGENT_WAITING, ADMIN_OWN, LIVE, RESEARCHED]
    assert page.counts == {"FACTS": 4, "TESTIMONY": 0, "STRUCTURE": 0, "READINGS": 0, "STAGES": 0}
    assert ADMIN_OWN not in ids(await listed(session, people.admin))
    assert await listed(session, people.researcher) == ReviewQueuePage(
        kinds=[], counts={}, total=0, items=[], next_cursor=None
    )


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({"origin": "AGENT"}, [AGENT_WAITING, PROPOSAL]),
        ({"origin": "CONTRIBUTION"}, [LIVE, PICTURE]),
        ({"origin": "RESEARCH"}, [RESEARCHED]),
        ({"origin": "TESTIMONY"}, []),
        ({"kind": "IMAGES"}, [PICTURE]),
        ({"kind": "FACTS", "origin": "AGENT"}, [AGENT_WAITING]),
    ],
)
async def test_the_kind_and_origin_filters_keep_only_their_items(
    seeded: tuple[AsyncSession, People], filters: dict[str, Any], expected: list[uuid.UUID]
) -> None:
    session, people = seeded
    page = await listed(session, people.admin, **filters)
    assert (ids(page), page.total) == (expected, len(expected))


async def test_the_craft_filter_keeps_only_that_craft_and_an_unknown_craft_is_refused(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    other = await seed_testimony(session)
    page = await listed(session, people.admin, craft_slug=other.craft.slug)
    assert ids(page) == [other.contribution.id]
    with pytest.raises(UnknownCraft):
        await listed(session, people.admin, craft_slug="No-Such-Craft-Anywhere")


async def test_the_pages_follow_one_another_without_repeating(seeded: tuple[AsyncSession, People]) -> None:
    session, people = seeded
    first = await listed(session, people.admin, limit=2)
    second = await listed(session, people.admin, limit=2, cursor=first.next_cursor)
    third = await listed(session, people.admin, limit=2, cursor=second.next_cursor)
    assert [ids(first), ids(second), ids(third)] == [EVERY_PENDING[:2], EVERY_PENDING[2:4], EVERY_PENDING[4:]]
    assert third.next_cursor is None and first.total == 5


async def test_a_fact_carries_its_quotes_sources_gates_and_the_facts_it_differs_from(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    page = await listed(session, people.admin, kind="FACTS", origin="AGENT")
    (item,) = page.items
    assert isinstance(item, FactItem)
    assert (item.origin, item.craft is not None and item.craft.slug) == ("AGENT", SLUG)
    fact = item.fact
    assert (fact.statement, fact.status, fact.level, fact.field) == (
        "An indigo vat turns blue at its surface.",
        "DRAFT",
        "PROVISIONAL",
        "CHEMISTRY",
    )
    assert fact.concept is not None and (fact.concept.name, fact.concept.type) == ("Indigo", "MATERIAL")
    (source,) = fact.sources
    assert (source.title, source.licence, source.reliability) == ("Indigo vats", "CC-BY-4.0", "B")
    assert [(quote.text, quote.locator) for quote in source.quotes] == [("the vat is yellow-green", "p. 4")]
    assert [gate.gate for gate in fact.gates] == ["QUOTES", "SOURCE", "DUPLICATE", "NOVELTY"]
    duplicate = fact.gates[2]
    assert [(related.id, related.text) for related in duplicate.related] == [
        (HELD, "A reduced indigo vat is yellow-green.")
    ]
    assert fact.gates[3].model == "judge-model-1"


async def test_a_proposal_carries_its_considered_labels_and_a_picture_its_declaration(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    page = await listed(session, people.admin, kind="COMPONENTS")
    (proposal,) = page.items
    assert proposal.kind == "COMPONENTS"
    assert (proposal.component.label, proposal.component.considered_labels) == (
        "review-queue-test-craft/chemistry/vat-surface",
        ["shared/chemistry/indigo-reduction"],
    )
    assert [subject.key for subject in proposal.component.subjects] == [SLUG]
    assert len(proposal.component.closest) <= 3
    (picture,) = (await listed(session, people.admin, kind="IMAGES")).items
    assert picture.kind == "IMAGES"
    assert (picture.picture.caption, picture.picture.status, picture.picture.craft_slug) == (
        "The vat turns yellow-green",
        "PENDING",
        SLUG,
    )


async def test_testimony_waits_for_professors_with_its_words(seeded: tuple[AsyncSession, People]) -> None:
    session, people = seeded
    other = await seed_testimony(session)
    page = await listed(session, people.professor, craft_slug=other.craft.slug)
    (item,) = page.items
    assert item.kind == "TESTIMONY" and item.origin == "TESTIMONY"
    assert (item.testimony["id"], item.testimony["version"]) == (str(other.contribution.id), 1)
    assert item.craft is not None and item.craft.slug == other.craft.slug
    assert item.proposer is None
    named = await listed(session, people.admin, craft_slug=other.craft.slug)
    assert named.items[0].proposer is not None
    assert named.items[0].proposer.name == other.artisan.name
