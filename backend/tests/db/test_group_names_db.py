from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.media.rows import craft_facts
from app.models import Claim, Craft, CraftGroupName, StructureProposal
from app.research.review_queue import STRUCTURE, QueueApproval
from app.services import review_queue_decisions as decisions
from app.services.curation_import import import_curation
from app.services.group_names import craft_group_names

from .structure_seed import CRAFT, NOW, People, proposed, seeded_session, stored_page
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

AJRAKH = "Kutch-Ajrakh"
AJRAKH_NAMES = ("Abduljabbar M. Khatri", "Ismail Mohammad Khatri", "Khatri", "Maldhari")
NAMED_TEXT = "The Khatri printers of the delta wash the cloth twice. Alum binds the red dye to the cotton."
NAMED_QUOTE = "The Khatri printers of the delta wash the cloth twice"
NAME = {"kind": "GROUP_NAME", "name": "Khatri", "groupKind": "COMMUNITY"}


@pytest.fixture
async def seeded() -> AsyncIterator[tuple[AsyncSession, People]]:
    async for opened in seeded_session():
        yield opened


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        yield opened


async def _claims(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(Claim))).scalar_one()


async def test_an_approved_name_joins_the_craft_s_list_and_writes_no_fact_or_page(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    page, claims = await stored_page(session), await _claims(session)
    result = await proposed(
        session, people.researcher, NAME, text=NAMED_TEXT, quote=NAMED_QUOTE, statement=None, field=None
    )
    assert result.status == "PENDING", result.checks
    ref = decisions.ItemRef(STRUCTURE, result.proposal_id)
    await decisions.approve_item(session, ref, people.professor, QueueApproval(), now=NOW)
    row = await session.get(StructureProposal, result.proposal_id, populate_existing=True)
    assert row is not None and (row.status, row.claimId) == ("APPROVED", None)
    kept = (await session.scalars(select(CraftGroupName).where(CraftGroupName.craftId == CRAFT))).all()
    assert [(name.name, name.kind, name.origin, name.quote, name.proposalId) for name in kept] == [
        ("Khatri", "COMMUNITY", "PROPOSAL", NAMED_QUOTE, row.id)
    ]
    assert await stored_page(session) == page and await _claims(session) == claims
    assert await craft_group_names(session, [CRAFT]) == {CRAFT: ("Khatri",)}


async def test_a_name_no_quote_states_is_refused_and_lists_nothing(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    unnamed = "The printers of the delta wash the cloth twice"
    result = await proposed(
        session, people.professor, NAME, text=NAMED_TEXT, quote=unnamed, statement=None, field=None
    )
    assert (result.outcome, result.checks[0].check, result.checks[0].passed) == ("REFUSED", "STATED", False)
    assert await craft_group_names(session, [CRAFT]) == {}


async def test_the_dossier_import_lists_the_names_its_quotes_state_once_and_media_reads_them(
    session: AsyncSession,
) -> None:
    first = await import_curation(session)
    outcome = next(outcome for outcome in first.dossiers if outcome.craft_slug == AJRAKH)
    assert outcome.changed["groupNames"] == len(AJRAKH_NAMES)
    craft = await session.scalar(select(Craft).where(Craft.slug == AJRAKH))
    assert craft is not None
    kept = (await session.scalars(select(CraftGroupName).where(CraftGroupName.craftId == craft.id))).all()
    assert {name.origin for name in kept} == {"DOSSIER"}
    assert (await craft_facts(session, [craft]))[craft.id].group_names == AJRAKH_NAMES
    again = await import_curation(session)
    assert all("groupNames" not in outcome.changed for outcome in again.dossiers)
