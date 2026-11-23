from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import PlaceLookup
from app.services.place_lookups import PLACE_LOOKUP_REFRESH, StoredPlaces
from app.sources.reference.wikidata_places import PlaceCandidate, PlacePoint

pytestmark = pytest.mark.db

BHUJ = PlaceCandidate("Q233846", "Bhuj", "city in Kachchh district, Gujarat, India")
ANJAR = PlaceCandidate("Q588783", "Anjar", "town in Kachchh district of Gujarat, India")
NOW = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)


class CountingFinder:
    def __init__(self) -> None:
        self.names: list[str] = []
        self.items: list[list[str]] = []

    async def place_candidates(self, name: str) -> list[PlaceCandidate]:
        self.names.append(name)
        return [BHUJ] if name.strip().casefold() == "bhuj" else []

    async def place_points(self, item_ids: Sequence[str]) -> dict[str, PlacePoint]:
        self.items.append(list(item_ids))
        return {BHUJ.item_id: PlacePoint(23.25, 69.67)} if BHUJ.item_id in item_ids else {}


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await session.execute(delete(PlaceLookup))
            yield session
            await session.close()
        finally:
            await transaction.rollback()


def stored_places(session: AsyncSession, finder: CountingFinder, clock: list[datetime]) -> StoredPlaces:
    def sessions() -> AsyncSession:
        return AsyncSession(bind=session.bind, expire_on_commit=False, autoflush=False)

    async def live() -> CountingFinder:
        return finder

    return StoredPlaces(sessions, live, clock=lambda: clock[0])


async def test_a_place_search_is_asked_once_a_month_and_kept_with_what_it_found(
    session: AsyncSession,
) -> None:
    finder, clock = CountingFinder(), [NOW]
    places = stored_places(session, finder, clock)
    assert await places.place_candidates("Bhuj") == [BHUJ]
    assert await places.place_candidates("  BHUJ ") == [BHUJ]
    assert await places.place_candidates("Nowhere") == []
    assert await places.place_candidates("nowhere") == []
    assert finder.names == ["Bhuj", "Nowhere"]
    clock[0] = NOW + PLACE_LOOKUP_REFRESH + timedelta(seconds=1)
    assert await places.place_candidates("Bhuj") == [BHUJ]
    assert finder.names == ["Bhuj", "Nowhere", "Bhuj"]
    keys = set(await session.scalars(select(PlaceLookup.lookupKey)))
    assert keys == {"name:bhuj", "name:nowhere"}


async def test_an_item_s_point_or_its_absence_is_kept_and_only_unknown_items_are_asked(
    session: AsyncSession,
) -> None:
    finder, clock = CountingFinder(), [NOW]
    places = stored_places(session, finder, clock)
    assert await places.place_points([BHUJ.item_id, ANJAR.item_id]) == {
        BHUJ.item_id: PlacePoint(23.25, 69.67)
    }
    assert await places.place_points([ANJAR.item_id, BHUJ.item_id, BHUJ.item_id]) == {
        BHUJ.item_id: PlacePoint(23.25, 69.67)
    }
    assert finder.items == [[BHUJ.item_id, ANJAR.item_id]]
    answers = dict((await session.execute(select(PlaceLookup.lookupKey, PlaceLookup.answer))).tuples().all())
    assert answers == {
        f"item:{BHUJ.item_id}": {"latitude": 23.25, "longitude": 69.67},
        f"item:{ANJAR.item_id}": {"latitude": None, "longitude": None},
    }
