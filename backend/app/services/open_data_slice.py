from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.core.errors import InvalidInput
from app.data.craft_names import load_craft_names
from app.models import Craft
from app.retrieval.hybrid import craft_scope
from app.retrieval.statements import scope_claims

from .open_data_crafts import MERGED
from .open_data_scope import ReleaseScope
from .open_data_values import Row

__all__ = ["CRAFT_TABLES", "CraftSlice", "craft_slice", "sliced_rows", "with_datasets"]

CRAFT_TABLES = ("craft_places", "stages", "materials", "reactions", "native_names", "gi_records")
NO_CRAFT = "No craft has the slug {slug!r}; give the slug its page address shows, such as Kutch-Ajrakh."
MERGED_CRAFT = "{slug} is merged into another craft; release the craft it is merged into."


@dataclass(frozen=True)
class CraftSlice:
    scope: ReleaseScope
    claims: ColumnElement[bool]

    @property
    def slug(self) -> str:
        return str(self.scope.craft)


async def craft_slice(session: AsyncSession, slug: str) -> CraftSlice:
    craft = await session.scalar(
        select(Craft).where(Craft.slug == slug).options(defer(Craft.descriptorEmbedding))
    )
    if craft is None:
        raise InvalidInput(NO_CRAFT.format(slug=slug))
    if craft.status == MERGED:
        raise InvalidInput(MERGED_CRAFT.format(slug=slug))
    name = load_craft_names().display_name(craft.slug, craft.name)
    within = scope_claims(await craft_scope(session, craft.slug))
    return CraftSlice(scope=ReleaseScope(craft=craft.slug, name=name), claims=within)


def sliced_rows(rows: Mapping[str, list[Row]], craft: str) -> dict[str, list[Row]]:
    crafts = [row for row in rows["crafts"] if row["slug"] == craft]
    families = {row["family"] for row in crafts}
    categories = {row["category"] for row in crafts}
    kept = {name: list(found) for name, found in rows.items()}
    kept["crafts"] = crafts
    kept["families"] = [row for row in rows["families"] if row["slug"] in families]
    kept["categories"] = [row for row in rows["categories"] if row["slug"] in categories]
    for name in CRAFT_TABLES:
        kept[name] = [row for row in rows[name] if row["craft"] == craft]
    kept["components"] = [row for row in rows["components"] if row["craft"] in (craft, None)]
    return kept


def with_datasets(rows: Mapping[str, list[Row]], codes: Collection[str]) -> dict[str, list[Row]]:
    return {**rows, "datasets": [row for row in rows["datasets"] if row["code"] in codes]}
