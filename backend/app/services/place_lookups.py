from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import PlaceLookup
from app.sources.reference.wikidata_places import PlaceCandidate, PlacePoint

from .supply_places import PlaceFinder

__all__ = ["PLACE_LOOKUP_REFRESH", "StoredPlaces", "item_key", "name_key"]

PLACE_LOOKUP_REFRESH = timedelta(days=30)
NAME_PREFIX = "name:"
ITEM_PREFIX = "item:"

Clock = Callable[[], datetime]
Finder = Callable[[], Awaitable[PlaceFinder]]


def name_key(name: str) -> str:
    return NAME_PREFIX + " ".join(name.split()).casefold()


def item_key(item_id: str) -> str:
    return ITEM_PREFIX + item_id


class StoredPlaces:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], finder: Finder, *, clock: Clock | None = None
    ) -> None:
        self._sessions = sessions
        self._finder = finder
        self._asked: PlaceFinder | None = None
        self._clock = clock or (lambda: datetime.now(UTC))

    async def place_candidates(self, name: str) -> list[PlaceCandidate]:
        key = name_key(name)
        stored = await self._fresh([key])
        if key in stored:
            return [PlaceCandidate(**candidate) for candidate in stored[key]["candidates"]]
        found = await (await self._live()).place_candidates(name)
        answer = {"candidates": [_candidate(candidate) for candidate in found]}
        await self._keep({key: answer})
        return found

    async def place_points(self, item_ids: Sequence[str]) -> dict[str, PlacePoint]:
        wanted = list(dict.fromkeys(item_ids))
        stored = await self._fresh([item_key(item_id) for item_id in wanted])
        known = {item_id: stored[item_key(item_id)] for item_id in wanted if item_key(item_id) in stored}
        asked = [item_id for item_id in wanted if item_id not in known]
        if asked:
            found = await (await self._live()).place_points(asked)
            answers = {item_id: _point(found.get(item_id)) for item_id in asked}
            await self._keep({item_key(item_id): answer for item_id, answer in answers.items()})
            known.update(answers)
        return {
            item_id: PlacePoint(answer["latitude"], answer["longitude"])
            for item_id, answer in known.items()
            if answer["latitude"] is not None and answer["longitude"] is not None
        }

    async def _live(self) -> PlaceFinder:
        if self._asked is None:
            self._asked = await self._finder()
        return self._asked

    async def _fresh(self, keys: Sequence[str]) -> dict[str, dict[str, Any]]:
        since = self._clock() - PLACE_LOOKUP_REFRESH
        async with self._sessions() as session:
            rows = await session.execute(
                select(PlaceLookup.lookupKey, PlaceLookup.answer).where(
                    PlaceLookup.lookupKey.in_(list(keys)), PlaceLookup.askedAt > since
                )
            )
            return dict(rows.tuples().all())

    async def _keep(self, answers: dict[str, dict[str, Any]]) -> None:
        if not answers:
            return
        now = self._clock()
        values = [{"lookupKey": key, "answer": answer, "askedAt": now} for key, answer in answers.items()]
        statement = insert(PlaceLookup).values(values)
        async with self._sessions() as session:
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[PlaceLookup.lookupKey],
                    set_={"answer": statement.excluded.answer, "askedAt": statement.excluded.askedAt},
                )
            )
            await session.commit()


def _candidate(candidate: PlaceCandidate) -> dict[str, Any]:
    return {"item_id": candidate.item_id, "label": candidate.label, "description": candidate.description}


def _point(point: PlacePoint | None) -> dict[str, Any]:
    if point is None:
        return {"latitude": None, "longitude": None}
    return {"latitude": point.latitude, "longitude": point.longitude}
