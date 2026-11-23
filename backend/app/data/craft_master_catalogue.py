from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping
from typing import Any

from .craft_master_loader import ACTIVE, MasterCraft, SharedCodes, codes_normalise, seed_plan

__all__ = ["build_catalogue"]

Plan = Mapping[str, list[dict[str, Any]]]


def build_catalogue(
    crafts: tuple[MasterCraft, ...] | None = None,
    codes: SharedCodes | None = None,
    aliases: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan = seed_plan(crafts, codes, aliases)
    rows = _catalogue_crafts(plan)
    digest = hashlib.sha256()
    for row in rows:
        digest.update(f"c{row['id']}{row['name']}{row['aliases']}".encode())
    return {"version": digest.hexdigest(), "categories": _catalogue_categories(plan), "crafts": rows}


def _catalogue_categories(plan: Plan) -> list[dict[str, Any]]:
    count_by_sub = Counter(row["subCategoryId"] for row in plan["crafts"])
    return [
        {
            **{key: value for key, value in category.items() if key != "masterId"},
            "subCategories": [
                {
                    "id": sub["id"],
                    "slug": sub["slug"],
                    "name": sub["name"],
                    "sortOrder": sub["sortOrder"],
                    "craftCount": count_by_sub[sub["id"]],
                }
                for sub in plan["subCategories"]
                if sub["categoryId"] == category["id"]
            ],
        }
        for category in plan["categories"]
    ]


def _catalogue_crafts(plan: Plan) -> list[dict[str, Any]]:
    by_code: dict[str, set[str]] = {}
    for row in plan["spellings"]:
        by_code.setdefault(row["craftCode"], set()).add(row["spelling"])
    extra: dict[str, set[str]] = {}
    for row in plan["aliases"]:
        if row["status"] == ACTIVE:
            extra.setdefault(row["craftId"], set()).add(row["aliasNorm"])
    category_of = {sub["id"]: sub["categoryId"] for sub in plan["subCategories"]}
    rows = []
    for craft in plan["crafts"]:
        names = set(by_code.get(craft["craftCode"] or "", set())) | extra.get(craft["id"], set())
        names -= {codes_normalise(craft["name"]), ""}
        rows.append(_catalogue_craft(craft, category_of.get(craft["subCategoryId"]), sorted(names)))
    return rows


def _catalogue_craft(craft: Mapping[str, Any], category_id: str | None, names: list[str]) -> dict[str, Any]:
    return {
        "id": craft["id"],
        "slug": craft["slug"],
        "name": craft["name"],
        "localName": None,
        "categoryId": category_id,
        "subCategoryId": craft["subCategoryId"],
        "sourceSerial": craft["sourceSerial"],
        "stateOfOrigin": craft["stateOfOrigin"],
        "stateOfPractice": craft["stateOfPractice"],
        "giStatus": craft["giStatus"],
        "isCatchAll": craft["isCatchAll"],
        "craftCode": craft["craftCode"],
        "aliases": names,
    }
