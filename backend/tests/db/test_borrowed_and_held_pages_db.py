from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput, Refused
from app.models import AuditLog, ComponentProposal, KnowledgePiece, PageLayout, TrustTierOverride
from app.research.page_drafts import DraftAddition
from app.research.page_proposals import PageBundle, PageProposalResult, PageSubject
from app.services.monograph_generated_parts import held_rows, subject_components
from app.services.open_work_subjects import subject_by_key
from app.services.page_drafts import add_to_draft, bundle_of, create_draft
from app.services.page_holds import HoldPlace, UnknownHold, confirm_hold, discard_hold, held_page, hold_page
from app.services.page_preview import preview_page
from app.services.page_proposals import propose_page
from app.services.trust_tiers import publishes_at_once

from ..research.general_spec_fixtures import table_units
from .component_lifecycle_seed import (
    ADMIN,
    BARE_CLAIM,
    FOREIGN,
    NEW,
    NOW,
    PROPOSER,
    SITE,
    STRANGER,
    lifecycle_seed,
    person,
    replacement,
)
from .page_documents_seed import (
    BARE_SLUG,
    CATEGORY_CLAIM,
    CATEGORY_SLUG,
    CONCEPT_PLAYER,
    CRAFT_CLAIM,
    CRAFT_SLUG,
    FAMILY_CLAIM,
    FAMILY_SLUG,
)
from .test_page_bundles_db import tools
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

SUBJECT = {"kind": "craft", "slug": CRAFT_SLUG}
BORROWED = (
    f"{FOREIGN} is borrowed from the shared library and its units cite 1 fact this page does not hold "
    f"({BARE_CLAIM}). Build Page Docs Test Craft's own fact_table on its own facts in this draft or bundle, "
    "and place that instead."
)
PLACE = HoldPlace(site=SITE, client_name="Claude", now=NOW)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await lifecycle_seed(opened)
        yield opened


def placed(*labels: str) -> dict[str, Any]:
    entries = [
        {"ref": label, "chapter": "chemistry", "order": n, "role": "FIGURE"}
        for n, label in enumerate(labels, 1)
    ]
    return {"baseVersion": 0, "entries": entries}


def linked(label: str, kind: str) -> dict[str, Any]:
    proposal = {
        "label": label,
        "extends": label,
        "extension": "SUBJECT_LINK",
        "title": "The family's alum figure on this page",
        "description": "Links the library's alum figure to this craft's page, where its facts are held.",
        "kind": kind,
        "field": "CHEMISTRY",
        "craftSlug": CRAFT_SLUG,
        "subjects": [{"kind": "CRAFT", "key": CRAFT_SLUG}],
    }
    return {"proposal": proposal}


async def test_a_borrowed_component_citing_facts_the_page_does_not_hold_is_refused_at_edit_preview_and_propose(
    session: AsyncSession,
) -> None:
    user = await person(session, PROPOSER)
    draft = await create_draft(session, user, PageSubject.model_validate(SUBJECT), now=NOW)
    for added in ({"layout": placed(FOREIGN)}, {"components": [linked(FOREIGN, "fact_table")]}):
        with pytest.raises(InvalidInput) as refused:
            await add_to_draft(session, user, draft.id, DraftAddition.model_validate(added), now=NOW)
        assert str(refused.value) == BORROWED
    bundle = PageBundle.model_validate(
        {"subject": SUBJECT, "components": [linked(FOREIGN, "fact_table")], "layout": placed(FOREIGN)}
    )
    previewed = await preview_page(session, user, bundle, site=SITE, now=NOW)
    proposed = await propose_page(session, user, bundle, tools=tools(), now=NOW)
    for parts in (previewed.parts, proposed.parts):
        assert [(part.part, part.outcome, part.message) for part in parts] == [
            ("component", "REFUSED", BORROWED),
            ("layout", "REFUSED", BORROWED),
        ]
    assert (
        await session.scalar(
            select(func.count()).select_from(ComponentProposal).where(ComponentProposal.label == FOREIGN)
        )
        == 0
    )


async def test_a_borrowed_component_whose_facts_the_page_holds_is_still_placed(session: AsyncSession) -> None:
    user = await person(session, PROPOSER)
    draft = await create_draft(session, user, PageSubject.model_validate(SUBJECT), now=NOW)
    kept = await add_to_draft(
        session, user, draft.id, DraftAddition.model_validate({"layout": placed(CONCEPT_PLAYER)}), now=NOW
    )
    assert kept.parts["layout"]["entries"][0]["ref"] == CONCEPT_PLAYER
    bundle = PageBundle.model_validate(
        {
            "subject": SUBJECT,
            "components": [linked(CONCEPT_PLAYER, "reaction_player")],
            "layout": placed(CONCEPT_PLAYER),
        }
    )
    previewed = await preview_page(session, user, bundle, site=SITE, now=NOW)
    assert [(part.part, part.outcome) for part in previewed.parts] == [
        ("component", "SHOWN"),
        ("layout", "SHOWN"),
    ]
    proposed = await propose_page(session, user, bundle, tools=tools(), now=NOW)
    assert [(part.part, part.outcome) for part in proposed.parts] == [
        ("component", "ACCEPTED"),
        ("layout", "ACCEPTED"),
    ]


async def test_the_page_draws_a_borrowed_component_only_when_it_holds_every_fact_its_units_cite(
    session: AsyncSession,
) -> None:
    subject = await subject_by_key(session, "craft", CRAFT_SLUG)
    labels = {component.label for component in await subject_components(session, subject, [])}
    assert CONCEPT_PLAYER in labels
    assert FOREIGN not in labels


async def _shared(session: AsyncSession) -> list[KnowledgePiece]:
    rows = await session.scalars(
        select(KnowledgePiece).where(KnowledgePiece.label.in_([CONCEPT_PLAYER, FOREIGN]))
    )
    return sorted(rows.all(), key=lambda row: str(row.label))


async def test_a_family_page_draws_a_shared_figure_on_the_science_its_own_facts_tell(
    session: AsyncSession,
) -> None:
    shared = await _shared(session)
    family = await subject_by_key(session, "family", FAMILY_SLUG)
    assert [row.label for row in await held_rows(session, family, shared, [FAMILY_CLAIM])] == [CONCEPT_PLAYER]
    assert await held_rows(session, family, shared, []) == []


async def test_a_category_page_holds_the_facts_of_the_crafts_on_its_shelves_whatever_its_own_facts_tell(
    session: AsyncSession,
) -> None:
    shared = await _shared(session)
    category = await subject_by_key(session, "category", CATEGORY_SLUG)
    for told in ([CATEGORY_CLAIM], []):
        drawn = [row.label for row in await held_rows(session, category, shared, told)]
        assert drawn == [CONCEPT_PLAYER, FOREIGN], told


async def test_a_craft_page_holds_a_shared_figure_by_its_own_facts_whatever_science_it_tells(
    session: AsyncSession,
) -> None:
    shared = await _shared(session)
    bare = await subject_by_key(session, "craft", BARE_SLUG)
    assert CONCEPT_PLAYER not in [row.label for row in await held_rows(session, bare, shared, [CRAFT_CLAIM])]
    craft = await subject_by_key(session, "craft", CRAFT_SLUG)
    assert [row.label for row in await held_rows(session, craft, shared, [])] == [CONCEPT_PLAYER]


async def test_only_an_account_whose_proposals_reach_readers_at_once_has_its_pages_held(
    session: AsyncSession,
) -> None:
    assert await publishes_at_once(session, ADMIN, "AGENT") is True
    assert await publishes_at_once(session, PROPOSER, "AGENT") is False
    session.add(
        TrustTierOverride(userId=PROPOSER, tier="PROVEN", note="Proven by hand.", setById=ADMIN, setAt=NOW)
    )
    await session.flush()
    assert await publishes_at_once(session, PROPOSER, "AGENT") is True


def whole_page() -> dict[str, Any]:
    component = {"proposal": replacement(replaces=None, units=table_units(FAMILY_CLAIM)), "cites": {}}
    return {"components": [component], "layout": placed(NEW)}


async def counts(session: AsyncSession) -> tuple[int, int, int]:
    proposals = await session.scalar(
        select(func.count()).select_from(ComponentProposal).where(ComponentProposal.label == NEW)
    )
    pieces = await session.scalar(
        select(func.count()).select_from(KnowledgePiece).where(KnowledgePiece.label == NEW)
    )
    layouts = await session.scalar(
        select(func.count()).select_from(PageLayout).where(PageLayout.entries.contains([{"ref": NEW}]))
    )
    return int(proposals or 0), int(pieces or 0), int(layouts or 0)


async def test_a_trusted_account_s_page_waits_for_one_confirmation_then_is_proposed(
    session: AsyncSession,
) -> None:
    admin = await person(session, ADMIN)
    draft = await create_draft(session, admin, PageSubject.model_validate(SUBJECT), now=NOW)
    draft = await add_to_draft(session, admin, draft.id, DraftAddition.model_validate(whole_page()), now=NOW)
    held = await hold_page(session, admin, bundle_of(draft), draft, PLACE)
    assert held.held is not None and (held.accepted, held.refused, held.parts) == (0, 0, [])
    assert held.held.confirm_url == f"{SITE}/contributions/pages/{held.held.id}"
    assert held.held.expires_at == NOW + timedelta(days=3)
    assert await counts(session) == (0, 0, 0)
    view = await held_page(session, admin, held.held.id, site=SITE, now=NOW)
    assert (view.state, view.counts.components, view.counts.layout, view.client_name) == (
        "WAITING",
        1,
        1,
        "Claude",
    )
    with pytest.raises(UnknownHold):
        await held_page(session, await person(session, STRANGER), held.held.id, site=SITE, now=NOW)

    async def proposed(bundle: PageBundle) -> PageProposalResult:
        return await propose_page(session, admin, bundle, tools=tools(), now=NOW)

    confirmed = await confirm_hold(session, admin, held.held.id, proposed, PLACE)
    assert confirmed.state == "CONFIRMED" and confirmed.result is not None
    assert (confirmed.result.accepted, confirmed.result.refused) == (2, 0)
    assert await counts(session) == (1, 1, 1)
    assert (draft.state, draft.result is not None) == ("SUBMITTED", True)
    with pytest.raises(Refused, match="confirmed"):
        await confirm_hold(session, admin, held.held.id, proposed, PLACE)
    actions = set(
        (await session.scalars(select(AuditLog.action).where(AuditLog.targetId == str(held.held.id)))).all()
    )
    assert actions == {"page.held", "page.hold_confirmed"}


async def test_a_discarded_replaced_or_expired_held_page_proposes_nothing(session: AsyncSession) -> None:
    admin = await person(session, ADMIN)
    bundle = PageBundle.model_validate({"subject": SUBJECT, **whole_page()})

    async def proposed(asked: PageBundle) -> PageProposalResult:
        raise AssertionError("nothing is proposed from a hold that is not waiting")

    first = (await hold_page(session, admin, bundle, None, PLACE)).held
    second = (await hold_page(session, admin, bundle, None, PLACE)).held
    assert first is not None and second is not None
    assert (await held_page(session, admin, first.id, site=SITE, now=NOW)).state == "DISCARDED"
    assert (await discard_hold(session, admin, second.id, PLACE)).state == "DISCARDED"
    third = (await hold_page(session, admin, bundle, None, PLACE)).held
    assert third is not None
    late = HoldPlace(site=SITE, client_name=None, now=NOW + timedelta(days=3))
    with pytest.raises(Refused, match="expired"):
        await confirm_hold(session, admin, third.id, proposed, late)
    assert await counts(session) == (0, 0, 0)
