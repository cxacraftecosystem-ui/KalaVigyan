from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Craft
from app.services.component_library import library_components
from app.services.component_places import PlacesHeld
from app.services.component_places_held import subject_places
from app.services.monograph_generated import generated_parts
from app.services.monograph_generated_assembly import assembled_document
from app.services.monograph_generated_drawings import Drawings
from app.services.open_work_components import craft_component_kinds
from app.services.open_work_subjects import subject_by_key

from .component_places_seed import (
    AZAMGARH,
    CLAY_COLOURS,
    GUJARAT,
    KACHCHH,
    KACHCHH_RIVER,
    KUTCH_CATEGORY_SLUG,
    KUTCH_SLUG,
    MONOGRAPH,
    RAINFALL,
    SHARED_PLAYER,
    UP_CATEGORY_SLUG,
    UP_SLUG,
    UTTAR_PRADESH,
    delivered_pieces,
    seed,
)
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await seed(opened)
        yield opened


def drawings(root: Path) -> Drawings:
    specs = root / MONOGRAPH / "specs"
    specs.mkdir(parents=True)
    for label in (RAINFALL, SHARED_PLAYER):
        (specs / (label.replace("/", "__") + ".json")).write_text('{"setting": "figure"}', encoding="utf-8")
    return Drawings(root=root)


async def drawn_labels(session: AsyncSession, kind: str, slug: str, root: Path) -> set[str]:
    parts = await generated_parts(session, await subject_by_key(session, kind, slug))
    assert parts is not None
    document = assembled_document(parts, Drawings(root=root))
    assert document is not None
    return {component.label for component in document.content.components}


async def test_a_craft_is_about_the_districts_of_its_own_state_and_never_a_stray_one(
    session: AsyncSession,
) -> None:
    kutch = await subject_places(session, await subject_by_key(session, "craft", KUTCH_SLUG))
    azamgarh = await subject_places(session, await subject_by_key(session, "craft", UP_SLUG))
    assert kutch == PlacesHeld(frozenset({KACHCHH}), frozenset({GUJARAT}))
    assert azamgarh == PlacesHeld(frozenset({AZAMGARH}), frozenset({UTTAR_PRADESH}))


async def test_a_category_holds_the_places_of_the_crafts_on_its_shelves(session: AsyncSession) -> None:
    kutch = await subject_places(session, await subject_by_key(session, "category", KUTCH_CATEGORY_SLUG))
    azamgarh = await subject_places(session, await subject_by_key(session, "category", UP_CATEGORY_SLUG))
    assert KACHCHH in kutch.districts
    assert KACHCHH not in azamgarh.districts


async def test_the_library_offers_a_district_figure_only_to_the_craft_of_that_district(
    session: AsyncSession,
) -> None:
    kutch = [item.label for item in (await library_components(session, slug=KUTCH_SLUG)).components]
    azamgarh = [item.label for item in (await library_components(session, slug=UP_SLUG)).components]
    assert kutch == [RAINFALL]
    assert azamgarh == [SHARED_PLAYER]


async def test_the_library_reads_a_borrowed_piece_s_units_for_the_places_it_names(
    session: AsyncSession,
) -> None:
    await delivered_pieces(session)
    azamgarh = [item.label for item in (await library_components(session, slug=UP_SLUG)).components]
    assert azamgarh == [CLAY_COLOURS, SHARED_PLAYER]


async def test_the_library_fills_its_limit_after_refusing_another_place_s_piece(
    session: AsyncSession,
) -> None:
    await delivered_pieces(session)
    first = await library_components(session, slug=UP_SLUG, limit=1)
    assert [item.label for item in first.components] == [CLAY_COLOURS]
    assert KACHCHH_RIVER < CLAY_COLOURS


async def test_open_work_counts_a_district_figure_only_for_the_craft_of_that_district(
    session: AsyncSession,
) -> None:
    rows = await session.execute(select(Craft.slug, Craft.id).where(Craft.slug.in_([KUTCH_SLUG, UP_SLUG])))
    ids = dict(rows.tuples().all())
    kinds = await craft_component_kinds(session, [ids[KUTCH_SLUG], ids[UP_SLUG]])
    assert "chart" in kinds[ids[KUTCH_SLUG]]
    assert "chart" not in kinds[ids[UP_SLUG]]


async def test_a_page_from_another_state_never_draws_the_district_figure_and_one_from_the_district_does(
    session: AsyncSession, tmp_path: Path
) -> None:
    root = drawings(tmp_path).root
    assert await drawn_labels(session, "craft", KUTCH_SLUG, root) == {RAINFALL}
    assert await drawn_labels(session, "craft", UP_SLUG, root) == {SHARED_PLAYER}


async def test_only_the_category_holding_the_district_draws_its_figure(
    session: AsyncSession, tmp_path: Path
) -> None:
    root = drawings(tmp_path).root
    assert await drawn_labels(session, "category", KUTCH_CATEGORY_SLUG, root) == {RAINFALL, SHARED_PLAYER}
    assert await drawn_labels(session, "category", UP_CATEGORY_SLUG, root) == {SHARED_PLAYER}
