from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Boolean, ColumnElement, Select, event, func, literal_column, select
from sqlalchemy.orm import ORMExecuteState, Session

from app.models import Chunk, Claim

from .stamps import made_by_current_model

__all__ = [
    "ANY_CRAFT",
    "EF_SEARCH",
    "INDEX_CANDIDATES_PER_HIT",
    "INDEX_SCAN_OPTION",
    "INDEX_SCAN_SETTINGS",
    "ITERATIVE_SCAN",
    "reads_every_craft",
    "vector_ranking",
]

ANY_CRAFT: ColumnElement[bool] = literal_column("true", Boolean())
INDEX_SCAN_OPTION = "kv_vector_index_scan"
EF_SEARCH = 200
ITERATIVE_SCAN = "relaxed_order"
INDEX_CANDIDATES_PER_HIT = 8
INDEX_SCAN_SETTINGS = select(
    func.set_config("hnsw.iterative_scan", ITERATIVE_SCAN, True),
    func.set_config("hnsw.ef_search", str(EF_SEARCH), True),
)


def reads_every_craft(conditions: Sequence[ColumnElement[bool]]) -> bool:
    return any(condition is ANY_CRAFT for condition in conditions)


def vector_ranking(
    model: type[Claim] | type[Chunk],
    conditions: Sequence[ColumnElement[bool]],
    vector: Sequence[float],
    depth: int,
) -> Select[tuple[uuid.UUID]]:
    if reads_every_craft(conditions):
        return _index_nearest(model, conditions, vector, depth)
    return _exact_nearest(model, conditions, vector, depth)


def _exact_nearest(
    model: type[Claim] | type[Chunk],
    conditions: Sequence[ColumnElement[bool]],
    vector: Sequence[float],
    depth: int,
) -> Select[tuple[uuid.UUID]]:
    embedding: Any = model.embedding
    distance = embedding.cosine_distance(list(vector))
    stamped = [*conditions, made_by_current_model(model.embeddingModel)]
    scoped = (
        select(model.id.label("id"), distance.label("distance"))
        .where(*stamped, embedding.is_not(None))
        .cte("scoped")
        .prefix_with("MATERIALIZED")
    )
    return select(scoped.c.id).order_by(scoped.c.distance, scoped.c.id).limit(depth)


def _index_nearest(
    model: type[Claim] | type[Chunk],
    conditions: Sequence[ColumnElement[bool]],
    vector: Sequence[float],
    depth: int,
) -> Select[tuple[uuid.UUID]]:
    embedding: Any = model.embedding
    distance = embedding.cosine_distance(list(vector))
    nearest = (
        select(model.id.label("id"), distance.label("distance"))
        .where(embedding.is_not(None), made_by_current_model(model.embeddingModel))
        .order_by(distance)
        .limit(depth * INDEX_CANDIDATES_PER_HIT)
        .cte("nearest")
        .prefix_with("MATERIALIZED")
    )
    return (
        select(nearest.c.id)
        .join(model, model.id == nearest.c.id)
        .where(*conditions)
        .order_by(nearest.c.distance, nearest.c.id)
        .limit(depth)
        .execution_options(**{INDEX_SCAN_OPTION: True})
    )


@event.listens_for(Session, "do_orm_execute")
def _index_scan_settings(state: ORMExecuteState) -> None:
    if state.execution_options.get(INDEX_SCAN_OPTION):
        state.session.execute(INDEX_SCAN_SETTINGS)
