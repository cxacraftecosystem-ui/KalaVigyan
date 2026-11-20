import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import ComponentProposal, KnowledgePiece, KnowledgePieceSubject, User
from app.research.component_proposals import ComponentProposalDraft
from app.research.component_specs import checked_spec
from app.services.component_proposals import propose_component
from app.services.monograph_generated import generated_document
from app.services.review_queue_components import approve_component

from ..research.general_spec_fixtures import TABLE, table_units
from .page_documents_seed import ADMIN, CRAFT, CRAFT_CLAIM as FACT, CRAFT_SLUG, seed
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
RESEARCHER = uuid.UUID("9e0c0000-0000-4000-8000-000000000001")
PROFESSOR = uuid.UUID("9e0c0000-0000-4000-8000-000000000002")
LABEL = "page-docs-test-craft/chemistry/alum-mordant-table"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await seed(opened)
        for user_id, role in ((RESEARCHER, "RESEARCHER"), (PROFESSOR, "PROFESSOR")):
            opened.add(
                User(
                    id=user_id,
                    name=f"{role.title()} delivered",
                    email=f"{user_id.hex}@example.org",
                    role=role,
                )
            )
        await opened.flush()
        yield opened


def draft(**changes: Any) -> ComponentProposalDraft:
    values: dict[str, Any] = {
        "label": LABEL,
        "title": "Alum as the mordant of the red",
        "description": "A table of what alum does to the madder red on cotton, each line resting on its fact.",
        "kind": "general_table",
        "field": "CHEMISTRY",
        "craft_slug": CRAFT_SLUG,
        "subjects": [{"kind": "CRAFT", "key": CRAFT_SLUG}],
        "spec": TABLE,
        "units": table_units(FACT),
    }
    return ComponentProposalDraft.model_validate({**values, **changes})


async def person(session: AsyncSession, user_id: uuid.UUID) -> User:
    found = await session.get(User, user_id)
    assert found is not None
    return found


async def test_a_delivered_component_waits_with_its_checked_spec_and_the_facts_it_rests_on(
    session: AsyncSession,
) -> None:
    stored = await propose_component(session, await person(session, RESEARCHER), draft(), now=NOW)
    assert (stored.outcome, stored.status) == ("STORED", "PENDING")
    assert stored.message.startswith("Stored for review with its spec")
    row = await session.get(ComponentProposal, stored.proposal_id)
    assert row is not None
    assert row.spec == checked_spec("general_table", TABLE).model_dump(mode="json")
    assert sorted(row.units or {}) == ["u0001", "u0002", "u0003", "u0004", "u0005", "u0006"]
    assert row.claimIds == [FACT]
    assert await session.scalar(select(KnowledgePiece.id).where(KnowledgePiece.label == LABEL)) is None


async def test_approval_registers_it_and_the_craft_s_document_draws_it_with_its_units_cited(
    session: AsyncSession,
) -> None:
    stored = await propose_component(session, await person(session, RESEARCHER), draft(), now=NOW)
    assert stored.proposal_id is not None
    decided = await approve_component(
        session, stored.proposal_id, await person(session, ADMIN), note=None, now=NOW
    )
    assert decided.message.startswith("Approved and registered")
    piece = await session.scalar(select(KnowledgePiece).where(KnowledgePiece.label == LABEL))
    assert piece is not None
    assert (piece.kind, piece.facet, piece.craftId, piece.claimIds) == (
        "general_table",
        "CHEMISTRY",
        CRAFT,
        [FACT],
    )
    assert piece.payload["delivered"]["spec"] == checked_spec("general_table", TABLE).model_dump(mode="json")
    linked = await session.scalars(
        select(KnowledgePieceSubject.craftId).where(KnowledgePieceSubject.pieceId == piece.id)
    )
    assert linked.all() == [CRAFT]
    document = await generated_document(session, "craft", CRAFT_SLUG)
    assert document is not None
    spec = document.specs[LABEL]
    assert spec["head"] == {"title": "u5001", "caption": "u5002"}
    assert spec["rows"] == [{"cells": ["u5005", "u5006"]}]
    within = [entry.ref for entry in document.content.layout if entry.within == LABEL]
    assert within == ["u5001", "u5002", "u5003", "u5004", "u5005", "u5006"]
    assert document.content.citation_claims["u5006"] == [str(FACT)]
    assert document.content.units["u5003"].nodes == [{"m": "s", "c": ["Mordant"]}]
    component = next(entry for entry in document.content.components if entry.label == LABEL)
    assert (component.kind, component.chapter) == ("general_table", "chem")


async def test_a_proposal_without_a_spec_stores_no_delivery_as_sql_null(session: AsyncSession) -> None:
    stored = await propose_component(
        session, await person(session, RESEARCHER), draft(spec=None, units={}), now=NOW
    )
    assert stored.message.startswith("Stored for review: an Admin approves or rejects it.")
    empty = await session.scalars(
        select(ComponentProposal.id).where(
            ComponentProposal.spec.is_(None), ComponentProposal.units.is_(None)
        )
    )
    assert empty.all() == [stored.proposal_id]
    assert await session.scalar(select(ComponentProposal.claimIds)) == []


async def test_a_professor_s_delivered_component_is_registered_at_once(session: AsyncSession) -> None:
    stored = await propose_component(session, await person(session, PROFESSOR), draft(), now=NOW)
    assert (stored.status, stored.message) == (
        "APPROVED",
        "Registered at once in the library, because your account reviews components: every page it applies to "
        "draws it from its spec.",
    )
    assert (
        await session.scalar(select(KnowledgePiece.kind).where(KnowledgePiece.label == LABEL))
        == "general_table"
    )


@pytest.mark.parametrize(
    ("units", "says"),
    [
        ({"u0006": {"text": "Fixes the red in 1890", "claimIds": [str(FACT)]}}, "states 1890"),
        (
            {"u0006": {"text": "Fixes the red", "claimIds": [str(uuid.uuid4())]}},
            "no shown fact has as its id",
        ),
    ],
)
async def test_a_unit_rests_only_on_shown_facts_and_their_numbers(
    session: AsyncSession, units: dict[str, Any], says: str
) -> None:
    changed = draft(units={**table_units(FACT), **units})
    with pytest.raises(InvalidInput, match=says):
        await propose_component(session, await person(session, RESEARCHER), changed, now=NOW)
    assert await session.scalar(select(ComponentProposal.id).where(ComponentProposal.label == LABEL)) is None
