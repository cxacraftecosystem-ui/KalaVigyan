from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http_cache import PUBLIC_READ_MAX_AGE_SECONDS, body_version
from app.core.kept_value import KeptValue
from app.data.craft_families import CraftFamilies, load_craft_families
from app.data.craft_master_loader import codes_normalise
from app.data.craft_names import CraftNameEdits, load_craft_names
from app.data.district_register import load_district_register
from app.data.state_languages import load_state_languages
from app.models import Craft, CraftAlias, CraftCategory, CraftSpelling, CraftSubCategory
from app.models.base import Base
from app.research.craft_catalogue import (
    CatalogueCategory,
    CatalogueCraft,
    CatalogueCraftRecord,
    CatalogueSubCategory,
    CraftCatalogue,
)

from .catalogue_records import load_catalogue_extras
from .catalogue_rows import (
    EMPTY_DEPTH,
    NO_EXTRAS,
    CatalogueExtras,
    catalogue_concepts,
    catalogue_summary,
    is_reader_craft,
    keys_of,
    local_name_of,
)
from .craft_page_family import reader_name

__all__ = [
    "CATALOGUE_KEPT_SECONDS",
    "CatalogueEditorial",
    "assemble_catalogue",
    "catalogue_editorial",
    "load_catalogue",
    "new_catalogue_cache",
    "reader_catalogue",
    "reference_counts",
    "reference_tables",
]

ACTIVE = "ACTIVE"
UNPLACED = (10**6, 10**6, "")
REFERENCE_SKIP = frozenset({"Craft", "CraftAlias"})
CATALOGUE_KEPT_SECONDS = PUBLIC_READ_MAX_AGE_SECONDS

Row = Mapping[str, Any]


@dataclass(frozen=True)
class CatalogueEditorial:
    families: CraftFamilies
    names: CraftNameEdits
    languages: Mapping[str, tuple[str, ...]]
    states: frozenset[str]


@dataclass(frozen=True)
class _RowContext:
    editorial: CatalogueEditorial
    extras: CatalogueExtras
    categories: Mapping[str, Row]
    sub_categories: Mapping[str, Row]
    spellings: Mapping[str, set[str]]
    aliases: Mapping[str, list[Row]]
    references: Mapping[str, int] | None


def catalogue_editorial() -> CatalogueEditorial:
    return CatalogueEditorial(
        families=load_craft_families(),
        names=load_craft_names(),
        languages=load_state_languages(),
        states=load_district_register().states,
    )


def assemble_catalogue(
    categories: Iterable[Row],
    sub_categories: Iterable[Row],
    crafts: Iterable[Row],
    spellings: Iterable[Row],
    aliases: Iterable[Row],
    *,
    include_inactive: bool = False,
    references: Mapping[str, int] | None = None,
    extras: CatalogueExtras = NO_EXTRAS,
    editorial: CatalogueEditorial | None = None,
) -> dict[str, Any]:
    category_rows = sorted(categories, key=lambda c: (c["sortOrder"], c["name"]))
    sub_rows = sorted(sub_categories, key=lambda s: (s["sortOrder"], s["name"]))
    context = _RowContext(
        editorial=editorial or catalogue_editorial(),
        extras=extras,
        categories={_text(c["id"]) or "": c for c in category_rows},
        sub_categories={_text(s["id"]) or "": s for s in sub_rows},
        spellings=_spellings(spellings),
        aliases=_active_aliases(aliases),
        references=(references or {}) if include_inactive else None,
    )
    order = _sub_order(category_rows, sub_rows)
    listed = [c for c in crafts if include_inactive or _status(c) == ACTIVE]
    rows = [_craft_row(craft, context) for craft in sorted(listed, key=lambda c: _craft_order(c, order))]
    readers = {row.id: row.slug for row in rows if is_reader_craft(row)}
    catalogue = CraftCatalogue(
        version="",
        summary=catalogue_summary(rows, extras.located, context.editorial.states),
        categories=_categories(category_rows, sub_rows, rows, context.editorial.families),
        concepts=catalogue_concepts(
            extras.concepts, readers, keys_of(name for row in rows for name in (row.name, row.display_name))
        ),
        crafts=rows,
    )
    body = catalogue.model_dump(mode="json", by_alias=True)
    body["version"] = body_version(body)
    return body


def _craft_row(craft: Row, context: _RowContext) -> CatalogueCraft:
    craft_id = _text(craft["id"]) or ""
    sub_id = _text(craft.get("subCategoryId"))
    sub = context.sub_categories.get(sub_id or "")
    category = context.categories.get(_text(sub["categoryId"]) or "") if sub else None
    family = context.editorial.families.family(category["slug"] if category else None)
    kind = context.editorial.families.kind(sub["slug"] if sub else None)
    fields: dict[str, Any] = {
        "id": craft_id,
        "slug": craft.get("slug"),
        "name": craft.get("name"),
        "display_name": reader_name(
            str(craft.get("slug")), str(craft.get("name")), catch_all=bool(craft.get("isCatchAll")), kind=kind
        ),
        "local_name": _local_name(craft, context),
        "category_id": _text(category["id"]) if category else None,
        "sub_category_id": sub_id,
        "family_label": family.label if family else None,
        "kind_label": kind.label if kind else None,
        "palette": family.palette if family else None,
        "source_serial": craft.get("sourceSerial"),
        "state_of_origin": list(craft.get("stateOfOrigin") or []),
        "state_of_practice": list(craft.get("stateOfPractice") or []),
        "gi_status": _enum(craft.get("giStatus")),
        "gi_year": context.extras.gi_years.get(craft_id),
        "is_catch_all": bool(craft.get("isCatchAll")),
        "craft_code": craft.get("craftCode"),
        "aliases": _alias_names(craft, context),
        "hero": context.extras.heroes.get(craft_id),
        "depth": context.extras.depth.get(craft_id, EMPTY_DEPTH),
    }
    if context.references is None:
        return CatalogueCraft(**fields)
    retired = _status(craft) != ACTIVE
    return CatalogueCraftRecord(
        **fields,
        status=_status(craft),
        merged_into_id=_text(craft.get("mergedIntoId")),
        reference_count=context.references.get(craft_id, 0) if retired else None,
    )


def _local_name(craft: Row, context: _RowContext) -> str | None:
    slug = str(craft.get("slug"))
    if craft.get("localName"):
        return str(craft["localName"])
    if context.editorial.names.sets_local_name(slug):
        return context.editorial.names.local_name(slug)
    states = [*(craft.get("stateOfOrigin") or []), *(craft.get("stateOfPractice") or [])]
    return local_name_of(
        states, context.aliases.get(_text(craft["id"]) or "", []), context.editorial.languages
    )


def _alias_names(craft: Row, context: _RowContext) -> list[str]:
    craft_id = _text(craft["id"]) or ""
    names = set(context.spellings.get(craft.get("craftCode") or "", set()))
    names |= {str(row["aliasNorm"]) for row in context.aliases.get(craft_id, [])}
    names.discard(codes_normalise(craft.get("name")))
    names.discard("")
    return sorted(names)


def _categories(
    category_rows: list[Row], sub_rows: list[Row], rows: list[CatalogueCraft], families: CraftFamilies
) -> list[CatalogueCategory]:
    active = [row for row in rows if getattr(row, "status", ACTIVE) == ACTIVE]
    counts = _count_by(row.sub_category_id for row in active)
    readers = _count_by(row.sub_category_id for row in active if not row.is_catch_all)
    payload = []
    for category in category_rows:
        category_id = _text(category["id"])
        subs = [
            CatalogueSubCategory(
                id=_text(sub["id"]) or "",
                slug=sub["slug"],
                name=sub["name"],
                label=_kind_label(families, sub["slug"]),
                sort_order=sub["sortOrder"],
                craft_count=counts.get(_text(sub["id"]) or "", 0),
                reader_count=readers.get(_text(sub["id"]) or "", 0),
            )
            for sub in sub_rows
            if _text(sub["categoryId"]) == category_id
        ]
        family = families.family(category["slug"])
        payload.append(
            CatalogueCategory(
                id=category_id or "",
                slug=category["slug"],
                name=category["name"],
                label=family.label if family else None,
                palette=family.palette if family else None,
                sort_order=category["sortOrder"],
                reader_count=sum(sub.reader_count for sub in subs),
                sub_categories=subs,
            )
        )
    return payload


def _kind_label(families: CraftFamilies, slug: str) -> str | None:
    kind = families.kind(slug)
    return kind.label if kind else None


def _count_by(keys: Iterable[str | None]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in keys:
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts


def _sub_order(category_rows: list[Row], sub_rows: list[Row]) -> dict[str, tuple[int, int, str]]:
    category_sort = {_text(c["id"]): c["sortOrder"] for c in category_rows}
    return {
        _text(sub["id"]) or "": (
            category_sort.get(_text(sub["categoryId"]), 10**6),
            sub["sortOrder"],
            sub["name"],
        )
        for sub in sub_rows
    }


def _craft_order(craft: Row, sub_order: Mapping[str, tuple[int, int, str]]) -> tuple[Any, ...]:
    serial = craft.get("sourceSerial")
    return (
        _status(craft) != ACTIVE,
        sub_order.get(_text(craft.get("subCategoryId")) or "", UNPLACED),
        serial is None,
        serial or 0,
        (craft.get("name") or "").lower(),
        _text(craft["id"]),
    )


def _spellings(rows: Iterable[Row]) -> dict[str, set[str]]:
    by_code: dict[str, set[str]] = {}
    for row in rows:
        if row.get("craftCode"):
            by_code.setdefault(row["craftCode"], set()).add(row["spelling"])
    return by_code


def _active_aliases(rows: Iterable[Row]) -> dict[str, list[Row]]:
    by_craft: dict[str, list[Row]] = {}
    for row in rows:
        if str(_enum(row.get("status")) or ACTIVE) == ACTIVE:
            by_craft.setdefault(_text(row["craftId"]) or "", []).append(row)
    return by_craft


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


def _enum(value: Any) -> Any:
    return getattr(value, "value", value)


def _status(craft: Row) -> str:
    return str(_enum(craft.get("status")) or ACTIVE)


def _rows(result: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in result.mappings().all()]


def reference_tables() -> list[Any]:
    return [
        table
        for name, table in sorted(Base.metadata.tables.items())
        if name not in REFERENCE_SKIP
        and "craftId" in table.c
        and any(fk.column.table.name == "Craft" for fk in table.c.craftId.foreign_keys)
    ]


async def reference_counts(session: AsyncSession, craft_ids: list[str]) -> dict[str, int]:
    counts: dict[str, int] = dict.fromkeys(craft_ids, 0)
    if not craft_ids:
        return counts
    for table in reference_tables():
        column = table.c.craftId
        result = await session.execute(
            select(column, func.count()).where(column.in_([uuid.UUID(i) for i in craft_ids])).group_by(column)
        )
        for craft_id, count in result.all():
            key = str(craft_id)
            if key in counts:
                counts[key] += int(count)
    return counts


async def load_catalogue(session: AsyncSession, *, include_inactive: bool = False) -> dict[str, Any]:
    categories = _rows(await session.execute(_category_query()))
    subs = _rows(await session.execute(_sub_category_query()))
    crafts = _rows(await session.execute(_craft_query(include_inactive)))
    spellings = _rows(await session.execute(select(CraftSpelling.spelling, CraftSpelling.craftCode)))
    aliases = _rows(await session.execute(_alias_query()))
    references: dict[str, int] = {}
    if include_inactive:
        references = await reference_counts(session, [str(c["id"]) for c in crafts if _status(c) != ACTIVE])
    return assemble_catalogue(
        categories,
        subs,
        crafts,
        spellings,
        aliases,
        include_inactive=include_inactive,
        references=references,
        extras=await load_catalogue_extras(session),
    )


def _category_query() -> Select[Any]:
    return select(CraftCategory.id, CraftCategory.slug, CraftCategory.name, CraftCategory.sortOrder)


def _sub_category_query() -> Select[Any]:
    return select(
        CraftSubCategory.id,
        CraftSubCategory.slug,
        CraftSubCategory.name,
        CraftSubCategory.categoryId,
        CraftSubCategory.sortOrder,
    )


def _craft_query(include_inactive: bool) -> Select[Any]:
    query = select(
        Craft.id,
        Craft.slug,
        Craft.name,
        Craft.localName,
        Craft.subCategoryId,
        Craft.sourceSerial,
        Craft.stateOfOrigin,
        Craft.stateOfPractice,
        Craft.giStatus,
        Craft.isCatchAll,
        Craft.craftCode,
        Craft.status,
        Craft.mergedIntoId,
    )
    return query if include_inactive else query.where(Craft.status == ACTIVE)


def _alias_query() -> Select[Any]:
    return select(
        CraftAlias.craftId,
        CraftAlias.alias,
        CraftAlias.aliasNorm,
        CraftAlias.script,
        CraftAlias.lang,
        CraftAlias.source,
        CraftAlias.status,
    ).where(CraftAlias.status == ACTIVE)


def new_catalogue_cache() -> KeptValue[dict[str, Any]]:
    return KeptValue(lifetime_seconds=CATALOGUE_KEPT_SECONDS)


async def reader_catalogue(session: AsyncSession, kept: KeptValue[dict[str, Any]]) -> dict[str, Any]:
    return await kept.value(lambda: load_catalogue(session))
