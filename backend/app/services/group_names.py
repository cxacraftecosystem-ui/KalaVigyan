from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.curation.dossier import Dossier
from app.curation.group_names import stated_group_names
from app.models import CraftGroupName, StructureProposal
from app.models.group_names import GROUP_NAME_LOCATOR_CHARS, GROUP_NAME_ORIGINS
from app.research.named_groups import group_name_key
from app.research.structure_proposals import GroupNameItem
from app.research.structure_proposals_values import stated_check

__all__ = [
    "DOSSIER_ORIGIN",
    "PROPOSAL_ORIGIN",
    "craft_group_names",
    "keep_dossier_group_names",
    "keep_proposed_group_name",
]

DOSSIER_ORIGIN, PROPOSAL_ORIGIN = GROUP_NAME_ORIGINS
UNSTATED = "No quote of structure proposal {id} states the name {name}"


async def craft_group_names(
    session: AsyncSession, craft_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, ...]]:
    if not craft_ids:
        return {}
    rows = await session.execute(
        select(CraftGroupName.craftId, CraftGroupName.name)
        .where(CraftGroupName.craftId.in_(list(craft_ids)))
        .order_by(CraftGroupName.craftId, CraftGroupName.nameKey)
    )
    found: dict[uuid.UUID, list[str]] = defaultdict(list)
    for craft_id, name in rows.tuples():
        found[craft_id].append(name)
    return {craft_id: tuple(names) for craft_id, names in found.items()}


async def keep_dossier_group_names(session: AsyncSession, craft_id: uuid.UUID, dossier: Dossier) -> int:
    rows = [
        _row(
            craft_id,
            GroupNameItem(name=stated.name, group_kind=stated.kind),
            source={"title": stated.source.title, "url": str(stated.source.url)},
            quote={"text": stated.quote.quote, "locator": stated.quote.locator},
        )
        | {"origin": DOSSIER_ORIGIN, "proposalId": None}
        for stated in stated_group_names(dossier)
    ]
    return await _kept(session, rows)


async def keep_proposed_group_name(
    session: AsyncSession, craft_id: uuid.UUID, proposal: StructureProposal, item: GroupNameItem
) -> int:
    stating = next(
        (
            (source, quote)
            for source in proposal.sources
            for quote in source["quotes"]
            if stated_check(item, [quote["text"]]).passed
        ),
        None,
    )
    if stating is None:
        raise InvalidInput(UNSTATED.format(id=proposal.id, name=item.name))
    source, quote = stating
    row = _row(craft_id, item, source=source, quote=quote)
    return await _kept(session, [row | {"origin": PROPOSAL_ORIGIN, "proposalId": proposal.id}])


def _row(
    craft_id: uuid.UUID, item: GroupNameItem, *, source: Mapping[str, Any], quote: Mapping[str, Any]
) -> dict[str, Any]:
    locator = quote.get("locator")
    return {
        "craftId": craft_id,
        "name": item.name,
        "nameKey": group_name_key(item.name),
        "kind": item.group_kind,
        "sourceTitle": str(source["title"]),
        "sourceUrl": str(source["url"]),
        "quote": str(quote["text"]),
        "locator": str(locator)[:GROUP_NAME_LOCATOR_CHARS] if locator else None,
    }


async def _kept(session: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> int:
    if not rows:
        return 0
    inserted = await session.execute(
        insert(CraftGroupName)
        .values(list(rows))
        .on_conflict_do_nothing(index_elements=["craftId", "nameKey"])
        .returning(CraftGroupName.id)
    )
    return len(inserted.all())
