from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import ColumnElement, String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

__all__ = [
    "EMBEDDING_RECIPE",
    "RECIPE_MARK",
    "StampRead",
    "current_embedding_model",
    "embedding_model_of",
    "made_by_current_model",
    "needs_model_vector",
    "needs_vector",
    "renewal_order",
    "stamp_reader",
]

RECIPE_MARK = "#"
EMBEDDING_RECIPE = "ctx1"
MODEL_PART = 1

StampRead = Callable[[], Awaitable[str | None]]


def current_embedding_model() -> ColumnElement[str]:
    return select(func.kv_embedding_model(type_=String())).scalar_subquery()


def embedding_model_of(stamp: Any) -> ColumnElement[str]:
    return func.split_part(stamp, RECIPE_MARK, MODEL_PART, type_=String())


def made_by_current_model(stamp: Any) -> ColumnElement[bool]:
    return embedding_model_of(stamp) == embedding_model_of(current_embedding_model())


def needs_vector(embedding: Any, stamp: Any) -> ColumnElement[bool]:
    return or_(embedding.is_(None), stamp.is_distinct_from(current_embedding_model()))


def needs_model_vector(embedding: Any, stamp: Any) -> ColumnElement[bool]:
    current = embedding_model_of(current_embedding_model())
    return or_(embedding.is_(None), embedding_model_of(stamp).is_distinct_from(current))


def renewal_order(embedding: Any, stamp: Any, updated_at: Any) -> list[ColumnElement[Any]]:
    readable = func.coalesce(made_by_current_model(stamp), False)
    return [embedding.is_not(None), readable, updated_at]


def stamp_reader(sessions: async_sessionmaker[AsyncSession]) -> StampRead:
    async def read() -> str | None:
        async with sessions() as session:
            return await session.scalar(select(current_embedding_model()))

    return read
