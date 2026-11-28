import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from types import MappingProxyType
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import ComponentProposal, LayoutProposal, User
from app.research.page_layout import PageLayoutEntry
from app.research.page_proposals import PageBundle, PartReport
from app.services import page_part_checks
from app.services.monograph_generated import generated_document
from app.services.open_work_subjects import subject_by_key
from app.services.page_layout_checks import MISSING, PUBLISHED_MISSING
from app.services.page_layouts import layout_of, store_layout
from app.services.page_preview import preview_page, previewed_document
from app.services.page_proposals import propose_page

from .page_documents_seed import CRAFT_CLAIM, CRAFT_PLAYER, CRAFT_SLUG, FAMILY_CLAIM, seed
from .test_page_bundles_db import FACT_PART, NOW, SITE, SUBJECT, component, tools
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

MAKER = uuid.UUID("9e0f0000-0000-4000-8000-000000000001")
REVIEWER = uuid.UUID("9e0f0000-0000-4000-8000-000000000002")
TABLE = "page-docs-test-craft/chemistry/alum-mordant-numbers"
UNKNOWN = "shared/climate/kachchh-annual-temperature-chart"
MISSING_CHART = "shared/climate/jaipur-annual-rainfall-chart"
REFUSING = "refused by the {part} check"
WHY = "It cites facts this page no longer holds, and a better table now replaces it."
GROUP_NAME = {
    "subject": SUBJECT,
    "item": {"kind": "GROUP_NAME", "name": "Khatri", "groupKind": "COMMUNITY"},
    "sources": [
        {
            "url": "https://example.org/printers",
            "title": "The printers of the town",
            "quotes": [{"text": "Khatri printers work in the town", "locator": "para 1"}],
        }
    ],
}
SECTION = {
    "field": "CHEMISTRY",
    "sentences": [{"text": "Alum fixes the madder red on the cotton.", "claim_ids": [str(CRAFT_CLAIM)]}],
}
EVERY_PART: Mapping[str, tuple[str, Any]] = MappingProxyType(
    {
        "fact": ("facts", [FACT_PART]),
        "structure": ("structure", [GROUP_NAME]),
        "component": ("components", [component(TABLE)]),
        "layout": ("layout", {"baseVersion": 0, "entries": []}),
        "picture": ("pictures", [{"claimIds": [str(CRAFT_CLAIM)]}]),
        "withdrawal": ("withdrawals", [{"label": CRAFT_PLAYER, "reason": WHY}]),
        "section": ("sections", [SECTION]),
    }
)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await seed(opened)
        for user_id, role in ((MAKER, "RESEARCHER"), (REVIEWER, "PROFESSOR")):
            opened.add(User(id=user_id, name=f"Parity {role}", email=f"{user_id.hex}@example.org", role=role))
        await opened.flush()
        yield opened


async def person(session: AsyncSession, user_id: uuid.UUID) -> User:
    found = await session.get(User, user_id)
    assert found is not None
    return found


def refusing(part: str) -> Callable[..., Awaitable[None]]:
    async def check(*_: Any) -> None:
        raise InvalidInput(REFUSING.format(part=part))

    return check


def considered(label: str, *labels: str, claim: uuid.UUID = CRAFT_CLAIM) -> dict[str, Any]:
    made = component(label)
    units = {
        ref: {**unit, "claimIds": [str(claim)]} if "claimIds" in unit else unit
        for ref, unit in made["proposal"]["units"].items()
    }
    return {"proposal": {**made["proposal"], "consideredLabels": list(labels), "units": units}, "cites": {}}


def placed(*labels: str) -> dict[str, Any]:
    entries = [
        {"ref": label, "chapter": "chem", "order": at, "role": "FIGURE"} for at, label in enumerate(labels, 1)
    ]
    return {"baseVersion": 0, "entries": entries}


def outcomes(parts: list[PartReport]) -> list[tuple[str, str, str]]:
    return [(part.part, part.outcome, part.message) for part in parts]


async def previewed_and_proposed(
    session: AsyncSession, bundle: PageBundle
) -> tuple[list[PartReport], list[PartReport]]:
    user = await person(session, MAKER)
    previewed = await previewed_document(session, user, bundle, now=NOW)
    proposed = await propose_page(session, user, bundle, tools=tools(), now=NOW)
    return previewed.reports, proposed.parts


async def test_the_preview_and_the_confirm_run_every_part_through_the_one_set_of_part_checks(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    checks = page_part_checks.PART_CHECKS
    assert set(EVERY_PART) == set(checks)
    monkeypatch.setattr(
        page_part_checks, "PART_CHECKS", MappingProxyType({part: refusing(part) for part in checks})
    )
    bundle = PageBundle.model_validate({"subject": SUBJECT, **dict(EVERY_PART.values())})
    previewed, proposed = await previewed_and_proposed(session, bundle)
    expected = sorted((part, "REFUSED", REFUSING.format(part=part)) for part in checks)
    assert sorted(outcomes(previewed)) == expected
    assert sorted(outcomes(proposed)) == expected
    assert await session.scalar(select(func.count()).select_from(ComponentProposal)) == 0


async def test_a_component_naming_a_label_the_library_lacks_is_refused_alike_and_a_registered_one_passes(
    session: AsyncSession,
) -> None:
    refused = PageBundle.model_validate({"subject": SUBJECT, "components": [considered(TABLE, UNKNOWN)]})
    said = f"{UNKNOWN} is not in the component library; list_components gives the labels."
    for parts in await previewed_and_proposed(session, refused):
        assert outcomes(parts) == [("component", "REFUSED", said)]
    assert await session.scalar(select(func.count()).select_from(ComponentProposal)) == 0
    kept = PageBundle.model_validate({"subject": SUBJECT, "components": [considered(TABLE, CRAFT_PLAYER)]})
    previewed, proposed = await previewed_and_proposed(session, kept)
    assert [(part.part, part.outcome) for part in previewed] == [("component", "SHOWN")]
    assert [(part.part, part.outcome) for part in proposed] == [("component", "ACCEPTED")]


async def test_a_component_restating_a_library_one_is_refused_alike_and_one_showing_other_facts_passes(
    session: AsyncSession,
) -> None:
    registered = PageBundle.model_validate({"subject": SUBJECT, "components": [considered(TABLE)]})
    reviewer = await person(session, REVIEWER)
    first = await propose_page(session, reviewer, registered, tools=tools(), now=NOW)
    assert [(part.outcome, part.status) for part in first.parts] == [("ACCEPTED", "APPROVED")]
    restated = PageBundle.model_validate({"subject": SUBJECT, "components": [considered(f"{TABLE}-again")]})
    for parts in await previewed_and_proposed(session, restated):
        (part,) = parts
        assert (part.part, part.outcome) == ("component", "REFUSED")
        assert part.message.startswith("1 component in the library already shows this")
        assert [(match.component.label, match.reasons) for match in part.matches] == [
            (TABLE, ["it rests on the same facts, 100% of them shared"])
        ]
    other = considered(f"{TABLE}-family", claim=FAMILY_CLAIM)
    previewed, proposed = await previewed_and_proposed(
        session, PageBundle.model_validate({"subject": SUBJECT, "components": [other]})
    )
    assert [(part.part, part.outcome) for part in previewed] == [("component", "SHOWN")]
    assert [(part.part, part.outcome) for part in proposed] == [("component", "ACCEPTED")]


async def test_a_layout_placing_a_component_its_bundle_failed_to_make_is_refused_and_never_written(
    session: AsyncSession,
) -> None:
    bundle = PageBundle.model_validate(
        {
            "subject": SUBJECT,
            "components": [considered(TABLE, UNKNOWN)],
            "layout": placed(TABLE, CRAFT_PLAYER),
        }
    )
    missing = MISSING.format(labels=TABLE)
    for parts in await previewed_and_proposed(session, bundle):
        assert [(part.part, part.outcome) for part in parts] == [
            ("component", "REFUSED"),
            ("layout", "REFUSED"),
        ]
        assert parts[1].message == missing
    assert await session.scalar(select(func.count()).select_from(LayoutProposal)) == 0
    assert await layout_of(session, await subject_by_key(session, "craft", CRAFT_SLUG)) is None


async def test_a_layout_placing_what_its_bundle_makes_and_the_library_holds_is_written(
    session: AsyncSession,
) -> None:
    bundle = PageBundle.model_validate(
        {
            "subject": SUBJECT,
            "components": [considered(TABLE, CRAFT_PLAYER)],
            "layout": placed(TABLE, CRAFT_PLAYER),
        }
    )
    previewed, proposed = await previewed_and_proposed(session, bundle)
    assert [(part.part, part.outcome) for part in previewed] == [("component", "SHOWN"), ("layout", "SHOWN")]
    assert [(part.part, part.outcome) for part in proposed] == [
        ("component", "ACCEPTED"),
        ("layout", "ACCEPTED"),
    ]
    assert await session.scalar(select(func.count()).select_from(LayoutProposal)) == 1


async def test_a_published_layout_naming_a_missing_component_draws_the_page_without_it_and_the_preview_says_so(
    session: AsyncSession,
) -> None:
    subject = await subject_by_key(session, "craft", CRAFT_SLUG)
    entries = [
        PageLayoutEntry.model_validate(entry) for entry in placed(CRAFT_PLAYER, MISSING_CHART)["entries"]
    ]
    await store_layout(session, subject, entries, actor=None)
    document = await generated_document(session, "craft", CRAFT_SLUG)
    assert document is not None
    assert MISSING_CHART not in {component.label for component in document.content.components}
    bundle = PageBundle.model_validate({"subject": SUBJECT, "facts": [FACT_PART]})
    previewed = await preview_page(session, await person(session, MAKER), bundle, site=SITE, now=NOW)
    assert [(part.part, part.outcome) for part in previewed.parts] == [
        ("fact", "SHOWN"),
        ("layout", "LISTED"),
    ]
    assert previewed.parts[1].message == PUBLISHED_MISSING.format(version=1, labels=MISSING_CHART)


async def test_a_published_layout_naming_only_what_exists_adds_no_notice(session: AsyncSession) -> None:
    subject = await subject_by_key(session, "craft", CRAFT_SLUG)
    entries = [PageLayoutEntry.model_validate(entry) for entry in placed(CRAFT_PLAYER)["entries"]]
    await store_layout(session, subject, entries, actor=None)
    bundle = PageBundle.model_validate({"subject": SUBJECT, "facts": [FACT_PART]})
    previewed = await preview_page(session, await person(session, MAKER), bundle, site=SITE, now=NOW)
    assert [(part.part, part.outcome) for part in previewed.parts] == [("fact", "SHOWN")]
