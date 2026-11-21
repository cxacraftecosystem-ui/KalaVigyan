import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ComponentProposal, LayoutProposal, User
from app.research.component_proposals import ComponentProposalDraft
from app.services.component_proposals import propose_component
from app.services.review_queue_components import component_items
from app.services.review_queue_layouts import layout_items

from ..research.general_spec_fixtures import TABLE, table_units
from .page_documents_seed import CRAFT, CRAFT_CLAIM as FACT, CRAFT_SLUG, CRAFT_TEXT, seed
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
PROPOSER = uuid.UUID("9e0f0000-0000-4000-8000-000000000001")
LAYOUT = uuid.UUID("9e0f0000-0000-4000-8000-0000000000c1")
LABEL = "page-docs-test-craft/chemistry/alum-review-table"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await seed(opened)
        opened.add(
            User(
                id=PROPOSER,
                name="Delivering researcher",
                email=f"{PROPOSER.hex}@example.org",
                role="RESEARCHER",
            )
        )
        await opened.flush()
        yield opened


async def delivered(session: AsyncSession) -> uuid.UUID:
    proposer = await session.get(User, PROPOSER)
    assert proposer is not None
    draft = ComponentProposalDraft.model_validate(
        {
            "label": LABEL,
            "title": "Alum as the mordant of the red",
            "description": "A table of what alum does to the madder red on cotton, each line resting on its fact.",
            "kind": "fact_table",
            "field": "CHEMISTRY",
            "craft_slug": CRAFT_SLUG,
            "subjects": [{"kind": "CRAFT", "key": CRAFT_SLUG}],
            "spec": TABLE,
            "units": table_units(FACT),
        }
    )
    stored = await propose_component(session, proposer, draft, now=NOW)
    assert stored.proposal_id is not None
    return stored.proposal_id


async def test_a_reviewer_sees_the_delivered_spec_drawn_its_units_and_the_facts_it_rests_on(
    session: AsyncSession,
) -> None:
    proposal = await delivered(session)
    (rendered,) = await component_items(session, [proposal])
    delivery = rendered.item.component.delivery
    assert delivery is not None and delivery.drawing is not None
    assert [component.label for component in delivery.drawing.content.components] == [LABEL]
    assert LABEL in delivery.drawing.specs
    assert len(delivery.drawing.content.units) == 6
    assert [unit.unit for unit in delivery.units] == ["u0001", "u0002", "u0003", "u0004", "u0005", "u0006"]
    assert [unit.claim_ids for unit in delivery.units][2:5] == [[], [], []]
    ((fact),) = delivery.facts
    assert (fact.id, fact.text, fact.shown) == (FACT, CRAFT_TEXT, True)
    assert fact.sources and fact.sources[0].quotes


async def test_the_page_review_draws_the_waiting_components_its_layout_places(session: AsyncSession) -> None:
    await delivered(session)
    session.add(
        LayoutProposal(
            id=LAYOUT,
            proposerId=PROPOSER,
            subjectKind="craft",
            craftId=CRAFT,
            baseVersion=0,
            entries=[{"ref": LABEL, "chapter": "chem", "order": 1, "role": "FIGURE"}],
            origin="AGENT",
        )
    )
    await session.flush()
    (rendered,) = await layout_items(session, [LAYOUT])
    (placed,) = rendered.item.layout.placed
    assert (placed.label, placed.kind) == (LABEL, "fact_table")
    assert placed.delivery.drawing is not None


async def test_a_component_given_without_a_spec_shows_no_drawing(session: AsyncSession) -> None:
    proposal = await delivered(session)
    row = await session.get(ComponentProposal, proposal)
    assert row is not None
    row.spec, row.units = None, None
    await session.flush()
    (rendered,) = await component_items(session, [proposal])
    assert rendered.item.component.delivery is None
