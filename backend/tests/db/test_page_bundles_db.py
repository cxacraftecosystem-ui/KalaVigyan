import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import ComponentProposal, LayoutProposal, PagePreview, User
from app.research.page_proposals import PageBundle
from app.services.page_preview import preview_page
from app.services.page_preview_links import UnknownPreview, preview_document
from app.services.page_proposals import PageTools, propose_page

from ..research.general_spec_fixtures import TABLE, table_units
from .page_documents_seed import BARE_SLUG, CRAFT_CLAIM as FACT, CRAFT_PLAYER, CRAFT_SLUG, seed
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
SITE = "https://kalavigyan.example"
RESEARCHER = uuid.UUID("9e0d0000-0000-4000-8000-000000000001")
STRANGER = uuid.UUID("9e0d0000-0000-4000-8000-000000000002")
SUBJECT = {"kind": "craft", "slug": CRAFT_SLUG}
HISTORY = "Printers in the town have dyed with alum since the eighteenth century."
FACT_PART = {
    "subject": SUBJECT,
    "field": "HISTORY",
    "statement": HISTORY,
    "sources": [
        {
            "url": "https://example.org/alum-history",
            "title": "A history of the town's printers",
            "quotes": [{"text": "printers in the town have dyed with alum since the eighteenth century"}],
        }
    ],
}


def component(label: str, *, craft: str = CRAFT_SLUG) -> dict[str, Any]:
    return {
        "proposal": {
            "label": label,
            "title": "Alum and the town's printers",
            "description": "A table of what alum does on the cotton and how long the town has printed with it.",
            "kind": "general_table",
            "field": "CHEMISTRY",
            "craftSlug": craft,
            "subjects": [{"kind": "CRAFT", "key": craft}],
            "spec": TABLE,
            "units": table_units(FACT),
        },
        "cites": {"u0002": ["fact:0"]},
    }


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await seed(opened)
        for user_id in (RESEARCHER, STRANGER):
            opened.add(
                User(id=user_id, name="Bundle maker", email=f"{user_id.hex}@example.org", role="RESEARCHER")
            )
        await opened.flush()
        yield opened


async def person(session: AsyncSession, user_id: uuid.UUID) -> User:
    found = await session.get(User, user_id)
    assert found is not None
    return found


def unused(*_: Any, **__: Any) -> Any:
    raise AssertionError("this bundle needs no fetch, gate or upload")


def tools() -> PageTools:
    nothing: Any = unused
    return PageTools(
        gates=nothing,
        fetcher=nothing,
        start_picture=nothing,
        spend=lambda kind: None,
        origin="AGENT",
        site=SITE,
    )


async def test_a_preview_draws_the_stored_page_with_the_bundle_s_fact_and_component_and_writes_no_proposal(
    session: AsyncSession,
) -> None:
    bundle = PageBundle.model_validate(
        {
            "subject": SUBJECT,
            "facts": [FACT_PART],
            "components": [component("page-docs-test-craft/chemistry/alum-print-table")],
        }
    )
    user = await person(session, RESEARCHER)
    previewed = await preview_page(session, user, bundle, site=SITE, now=NOW)
    assert [(part.part, part.outcome) for part in previewed.parts] == [
        ("fact", "SHOWN"),
        ("component", "SHOWN"),
    ]
    assert previewed.preview_url.startswith(f"{SITE}/preview/")
    assert previewed.page_url == f"{SITE}/crafts/{CRAFT_SLUG}"
    assert "history" in previewed.chapters and previewed.components >= 2
    token = previewed.preview_url.rsplit("/", 1)[1]
    document = await preview_document(session, user, token, now=NOW)
    units = document["content"]["units"]
    assert any(HISTORY.rsplit(" ", 1)[0] in str(unit["nodes"]) for unit in units.values())
    assert "page-docs-test-craft/chemistry/alum-print-table" in document["specs"]
    assert await session.scalar(select(ComponentProposal.id)) is None
    with pytest.raises(UnknownPreview):
        await preview_document(session, await person(session, STRANGER), token, now=NOW)
    assert (await session.scalars(select(PagePreview.userId))).all() == [RESEARCHER]


async def test_a_preview_refuses_a_part_that_would_be_refused_and_shows_the_rest(
    session: AsyncSession,
) -> None:
    bundle = PageBundle.model_validate(
        {
            "subject": SUBJECT,
            "components": [component("page-docs-test-bare/chemistry/alum-print-table", craft=BARE_SLUG)],
            "layout": {"baseVersion": 3, "entries": []},
            "pictures": [{"claimIds": [str(FACT)]}],
            "facts": [FACT_PART],
        }
    )
    previewed = await preview_page(session, await person(session, RESEARCHER), bundle, site=SITE, now=NOW)
    outcomes = {(part.part, part.outcome) for part in previewed.parts}
    assert outcomes == {
        ("fact", "SHOWN"),
        ("component", "REFUSED"),
        ("layout", "REFUSED"),
        ("picture", "LISTED"),
    }
    refused = next(part for part in previewed.parts if part.part == "layout")
    assert refused.message.startswith("The layout of Page-Docs-Test-Craft is at version 0, not 3.")


async def test_a_bundle_is_accepted_part_by_part_in_one_report(session: AsyncSession) -> None:
    bundle = PageBundle.model_validate(
        {
            "subject": SUBJECT,
            "components": [
                {**component("page-docs-test-craft/chemistry/alum-print-table"), "cites": {}},
                {**component("page-docs-test-bare/chemistry/alum-print-table", craft=BARE_SLUG), "cites": {}},
            ],
            "layout": {"baseVersion": 0, "entries": []},
        }
    )
    result = await propose_page(session, await person(session, RESEARCHER), bundle, tools=tools(), now=NOW)
    assert [(part.part, part.index, part.outcome) for part in result.parts] == [
        ("component", 0, "ACCEPTED"),
        ("component", 1, "REFUSED"),
        ("layout", 0, "ACCEPTED"),
    ]
    assert (result.accepted, result.refused) == (2, 1)
    assert result.parts[1].message == (
        "Component 1 is keyed to another craft: key it to Page-Docs-Test-Craft with craft_slug or a CRAFT subject."
    )
    stored = await session.scalars(select(ComponentProposal.label))
    assert stored.all() == ["page-docs-test-craft/chemistry/alum-print-table"]
    assert await session.scalar(select(LayoutProposal.status)) == "PENDING"


async def test_a_thin_page_cannot_be_previewed(session: AsyncSession) -> None:
    bundle = PageBundle.model_validate(
        {"subject": {"kind": "craft", "slug": BARE_SLUG}, "layout": {"baseVersion": 0, "entries": []}}
    )
    with pytest.raises(InvalidInput, match="too few published fields"):
        await preview_page(session, await person(session, RESEARCHER), bundle, site=SITE, now=NOW)


async def test_a_component_part_refused_for_a_close_match_names_the_matches_and_the_ways_on(
    session: AsyncSession,
) -> None:
    bundle = PageBundle.model_validate(
        {"subject": SUBJECT, "components": [{**component(CRAFT_PLAYER), "cites": {}}]}
    )
    result = await propose_page(session, await person(session, RESEARCHER), bundle, tools=tools(), now=NOW)
    (part,) = result.parts
    assert (part.part, part.outcome, part.id) == ("component", "REFUSED", None)
    assert CRAFT_PLAYER in [match.component.label for match in part.matches]
    assert len(part.ways_on) == 2 and part.ways_on[0].startswith("Place the existing component by its label")
    assert await session.scalar(select(ComponentProposal.id)) is None
