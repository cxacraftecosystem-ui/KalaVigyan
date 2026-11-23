import uuid
from itertools import batched
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.craft_master_loader import seed_plan
from app.models import Craft, CraftAlias, CraftCategory, CraftCode, CraftSpelling, CraftSubCategory

BATCH = 500

CRAFT_COLUMNS = (
    "name",
    "subCategoryId",
    "category",
    "sourceSerial",
    "stateOfOrigin",
    "stateOfPractice",
    "giStatus",
    "isCatchAll",
    "sourceNotes",
    "craftCode",
)

Rows = list[dict[str, Any]]
StoredCraft = tuple[uuid.UUID, Any]


def _uuid(value: Any) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


async def ids_by_slug(session: AsyncSession, model: Any) -> dict[str, uuid.UUID]:
    return dict((await session.execute(select(model.slug, model.id))).all())


async def seed_crafts(
    session: AsyncSession, plan: dict[str, list[dict[str, Any]]] | None = None
) -> dict[str, int]:
    if plan is None:
        plan = seed_plan()
    category_ids = await _seed_categories(session, plan["categories"])
    category_slugs = _seed_slugs(plan["categories"])
    sub_ids = await _seed_sub_categories(session, plan["subCategories"], category_ids, category_slugs)
    sub_slugs = _seed_slugs(plan["subCategories"])
    await _seed_codes(session, plan["codes"])
    await _seed_spellings(session, plan["spellings"])
    craft_slugs = await _seed_craft_rows(session, plan["crafts"], sub_ids, sub_slugs)
    alias_rows = _alias_rows(plan["aliases"], craft_slugs, await ids_by_slug(session, Craft))
    await _seed_aliases(session, alias_rows)
    await session.flush()
    return {
        "categories": len(plan["categories"]),
        "subCategories": len(plan["subCategories"]),
        "crafts": len(plan["crafts"]),
        "codes": len(plan["codes"]),
        "spellings": len(plan["spellings"]),
        "aliases": len(alias_rows),
    }


def _seed_slugs(rows: Rows) -> dict[uuid.UUID, str]:
    return {_uuid(row["id"]): row["slug"] for row in rows}


async def _seed_categories(session: AsyncSession, rows: Rows) -> dict[str, uuid.UUID]:
    for row in rows:
        values = {
            "id": _uuid(row["id"]),
            "slug": row["slug"],
            "name": row["name"],
            "sortOrder": row["sortOrder"],
        }
        await session.execute(
            insert(CraftCategory)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[CraftCategory.slug],
                set_={"name": values["name"], "sortOrder": values["sortOrder"]},
            )
        )
    return await ids_by_slug(session, CraftCategory)


async def _seed_sub_categories(
    session: AsyncSession,
    rows: Rows,
    category_ids: dict[str, uuid.UUID],
    category_slugs: dict[uuid.UUID, str],
) -> dict[str, uuid.UUID]:
    for row in rows:
        category_id = category_ids[category_slugs[_uuid(row["categoryId"])]]
        values = {
            "id": _uuid(row["id"]),
            "slug": row["slug"],
            "name": row["name"],
            "categoryId": category_id,
            "sortOrder": row["sortOrder"],
        }
        await session.execute(
            insert(CraftSubCategory)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[CraftSubCategory.slug],
                set_={"name": values["name"], "categoryId": category_id, "sortOrder": values["sortOrder"]},
            )
        )
    return await ids_by_slug(session, CraftSubCategory)


async def _seed_codes(session: AsyncSession, rows: Rows) -> None:
    for chunk in batched(rows, BATCH, strict=False):
        await session.execute(
            insert(CraftCode)
            .values([{"code": r["code"], "name": r["name"]} for r in chunk])
            .on_conflict_do_update(
                index_elements=[CraftCode.code], set_={"name": insert(CraftCode).excluded.name}
            )
        )


async def _seed_spellings(session: AsyncSession, rows: Rows) -> None:
    for chunk in batched(rows, BATCH, strict=False):
        await session.execute(
            insert(CraftSpelling)
            .values(
                [
                    {
                        "spelling": r["spelling"],
                        "label": r["label"],
                        "craftCode": r["craftCode"],
                        "source": r["source"],
                    }
                    for r in chunk
                ]
            )
            .on_conflict_do_nothing(index_elements=[CraftSpelling.spelling])
        )


async def _existing_crafts(session: AsyncSession) -> dict[str, StoredCraft]:
    return {
        slug: (row_id, meta)
        for slug, row_id, meta in (
            await session.execute(select(Craft.slug, Craft.id, Craft.extraMetadata))
        ).all()
    }


async def _seed_craft_rows(
    session: AsyncSession, rows: Rows, sub_ids: dict[str, uuid.UUID], sub_slugs: dict[uuid.UUID, str]
) -> dict[uuid.UUID, str]:
    existing = await _existing_crafts(session)
    craft_slugs: dict[uuid.UUID, str] = {}
    for row in rows:
        craft_slugs[_uuid(row["id"])] = row["slug"]
        found = existing.get(row["slug"])
        values = _craft_values(row, sub_ids[sub_slugs[_uuid(row["subCategoryId"])]], found)
        await _upsert_craft(session, row, values, found)
    return craft_slugs


def _craft_values(
    row: dict[str, Any], sub_category_id: uuid.UUID, found: StoredCraft | None
) -> dict[str, Any]:
    values = {column: row.get(column) for column in CRAFT_COLUMNS}
    values["subCategoryId"] = sub_category_id
    meta = dict(found[1] or {}) if found else {}
    meta.update(row.get("extraMetadata") or {})
    if row.get("masterId"):
        meta["masterId"] = row["masterId"]
    values["extraMetadata"] = meta
    return values


async def _upsert_craft(
    session: AsyncSession, row: dict[str, Any], values: dict[str, Any], found: StoredCraft | None
) -> None:
    if found is None:
        await session.execute(
            insert(Craft).values(
                id=_uuid(row["id"]), slug=row["slug"], status=row.get("status", "ACTIVE"), **values
            )
        )
    else:
        await session.execute(
            insert(Craft)
            .values(id=found[0], slug=row["slug"], **values)
            .on_conflict_do_update(index_elements=[Craft.slug], set_=values)
        )


def _alias_rows(rows: Rows, craft_slugs: dict[uuid.UUID, str], craft_ids: dict[str, uuid.UUID]) -> Rows:
    alias_rows = []
    for row in rows:
        slug = craft_slugs.get(_uuid(row["craftId"]))
        if slug is None or slug not in craft_ids:
            continue
        alias_rows.append(
            {
                "craftId": craft_ids[slug],
                "alias": str(row["alias"])[:300],
                "aliasNorm": str(row["aliasNorm"])[:300],
                "script": row.get("script"),
                "lang": row.get("lang"),
                "source": row["source"],
                "status": row.get("status", "ACTIVE"),
            }
        )
    return alias_rows


async def _seed_aliases(session: AsyncSession, rows: Rows) -> None:
    for chunk in batched(rows, BATCH, strict=False):
        await session.execute(
            insert(CraftAlias)
            .values(list(chunk))
            .on_conflict_do_nothing(index_elements=[CraftAlias.craftId, CraftAlias.aliasNorm])
        )
