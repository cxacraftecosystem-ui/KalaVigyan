from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgePiece

from .component_library_applies import APPLIED_CRAFT, APPLIED_PIECE, applies_to, registered_pieces

__all__ = ["CraftPiece", "craft_component_kinds", "craft_pieces", "registered_pieces"]


@dataclass(frozen=True)
class CraftPiece:
    craft_id: uuid.UUID
    label: str
    kind: str
    field: str
    fields: tuple[str, ...]

    def filed_under(self) -> tuple[str, ...]:
        return (self.field, *(other for other in self.fields if other != self.field))


async def craft_pieces(session: AsyncSession, craft_ids: Sequence[uuid.UUID]) -> list[CraftPiece]:
    if not craft_ids:
        return []
    applying = applies_to(craft_ids).subquery()
    rows = await session.execute(
        select(
            applying.c[APPLIED_CRAFT],
            KnowledgePiece.label,
            KnowledgePiece.kind,
            KnowledgePiece.facet,
            KnowledgePiece.fields,
        )
        .join(KnowledgePiece, KnowledgePiece.id == applying.c[APPLIED_PIECE])
        .where(*registered_pieces())
        .distinct()
    )
    return [
        CraftPiece(craft_id, str(label), kind, facet, tuple(fields or ()))
        for craft_id, label, kind, facet, fields in rows.all()
    ]


async def craft_component_kinds(
    session: AsyncSession, craft_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, frozenset[str]]:
    found: dict[uuid.UUID, set[str]] = defaultdict(set)
    for piece in await craft_pieces(session, craft_ids):
        found[piece.craft_id].add(piece.kind)
    return {craft_id: frozenset(kinds) for craft_id, kinds in found.items()}
