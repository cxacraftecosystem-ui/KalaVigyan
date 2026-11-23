from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent
MASTER_FILE = DATA_DIR / "craft_master_list.json"
ALIASES_FILE = DATA_DIR / "craft_master_aliases.json"
CODES_FILE = DATA_DIR / "cross_portal_codes.json"
VOCABULARY_FILE = DATA_DIR / "craft_vocabulary.txt"
CRAFT_ALIASES_FILE = DATA_DIR / "craft_aliases.json"
CRAFT_WIKIDATA_FILE = DATA_DIR / "craft_wikidata.json"
SEED_CLAIMS_FILE = DATA_DIR / "seed_claims.json"
SHA1_FILE = DATA_DIR.parents[2] / "shared" / "craft-master.sha1"

MASTER_COUNT = 455

ACTIVE = "ACTIVE"
LEGACY = "LEGACY"
MERGED = "MERGED"
STATUSES = (ACTIVE, LEGACY, MERGED)

GI = "GI"
NON_GI = "NON_GI"
GI_STATUSES = (GI, NON_GI)

ALL_INDIA = "All India"

ALIASES_KEY = "aliases"
MASTER_SEED_KEY = "masterSeed"

SOURCE_SHARED = "SHARED"

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class MasterCraft:
    category: str
    category_slug: str
    sub_category: str
    sub_category_slug: str
    source_serial: int
    name: str
    slug: str
    state_of_origin: tuple[str, ...]
    state_of_practice: tuple[str, ...]
    gi_status: str
    notes: tuple[str, ...]

    @property
    def is_catch_all(self) -> bool:
        return is_catch_all(self.notes)


@dataclass(frozen=True)
class MasterSubCategory:
    slug: str
    name: str
    sort_order: int


@dataclass(frozen=True)
class MasterCategory:
    slug: str
    name: str
    sort_order: int
    sub_categories: tuple[MasterSubCategory, ...]


@dataclass(frozen=True)
class CraftEntry:
    code: str
    name: str
    spellings: tuple[str, ...]


@dataclass(frozen=True)
class SharedCodes:
    version: int
    crafts: tuple[CraftEntry, ...]
    spelling_index: dict[str, str]

    def craft(self, code: str) -> CraftEntry | None:
        return next((c for c in self.crafts if c.code == code), None)


def is_catch_all(notes: Any) -> bool:
    return any("catch-all" in str(note).lower() for note in notes or ())


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_master(rows: list[dict[str, Any]]) -> tuple[MasterCraft, ...]:
    return tuple(
        MasterCraft(
            category=row["category"],
            category_slug=row["categorySlug"],
            sub_category=row["subCategory"],
            sub_category_slug=row["subCategorySlug"],
            source_serial=int(row["sourceSerial"]),
            name=row["craftName"],
            slug=row["craftSlug"],
            state_of_origin=tuple(row["stateOfOrigin"]),
            state_of_practice=tuple(row["stateOfPractice"]),
            gi_status=row["giStatus"],
            notes=tuple(row["notes"]),
        )
        for row in rows
    )


@lru_cache(maxsize=1)
def load_master() -> tuple[MasterCraft, ...]:
    return parse_master(_read_json(MASTER_FILE))


def categories_of(crafts: tuple[MasterCraft, ...]) -> tuple[MasterCategory, ...]:
    order: list[str] = []
    names: dict[str, str] = {}
    subs: dict[str, list[tuple[str, str]]] = {}
    for craft in crafts:
        if craft.category_slug not in names:
            order.append(craft.category_slug)
            names[craft.category_slug] = craft.category
            subs[craft.category_slug] = []
        pair = (craft.sub_category_slug, craft.sub_category)
        if pair not in subs[craft.category_slug]:
            subs[craft.category_slug].append(pair)
    return tuple(
        MasterCategory(
            slug=slug,
            name=names[slug],
            sort_order=index,
            sub_categories=tuple(
                MasterSubCategory(slug=s, name=n, sort_order=j)
                for j, (s, n) in enumerate(subs[slug], start=1)
            ),
        )
        for index, slug in enumerate(order, start=1)
    )


@lru_cache(maxsize=1)
def master_categories() -> tuple[MasterCategory, ...]:
    return categories_of(load_master())


@lru_cache(maxsize=1)
def load_aliases() -> dict[str, Any]:
    return _read_json(ALIASES_FILE)


def master_id(kind: str, slug: str) -> str:
    return f"cm{kind}{hashlib.md5(f'{kind}:{slug}'.encode()).hexdigest()[:22]}"


ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "craft-master.kalavigyan")


def seed_uuid(kind: str, slug: str) -> str:
    return str(uuid.uuid5(ID_NAMESPACE, master_id(kind, slug)))


def normalise(text: Any) -> str:
    if text is None:
        return ""
    from anyascii import anyascii

    folded = anyascii(unicodedata.normalize("NFC", str(text))).lower().replace("&", " and ")
    return " ".join(_NON_ALNUM.sub(" ", folded).split())


def codes_normalise(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()
    return " ".join(_NON_ALNUM.sub(" ", stripped).split())


def parse_codes(raw: dict[str, Any]) -> SharedCodes:
    crafts = tuple(
        CraftEntry(code=c["code"], name=c["name"], spellings=tuple(c["spellings"])) for c in raw["crafts"]
    )
    spelling_index: dict[str, str] = {}
    for craft in crafts:
        for spelling in (craft.name, *craft.spellings):
            spelling_index.setdefault(codes_normalise(spelling), craft.code)
    return SharedCodes(version=int(raw["version"]), crafts=crafts, spelling_index=spelling_index)


@lru_cache(maxsize=1)
def shared_codes() -> SharedCodes:
    return parse_codes(_read_json(CODES_FILE))


def shared_craft_code(name: str | None, codes: SharedCodes | None = None) -> str | None:
    key = codes_normalise(name)
    return (codes or shared_codes()).spelling_index.get(key) if key else None


def token_set_ratio(a: Any, b: Any) -> float:
    ta, tb = set(normalise(a).split()), set(normalise(b).split())
    if not ta or not tb:
        return 0.0
    both = " ".join(sorted(ta & tb))
    first = " ".join(filter(None, (both, " ".join(sorted(ta - tb)))))
    second = " ".join(filter(None, (both, " ".join(sorted(tb - ta)))))

    def ratio(x: str, y: str) -> float:
        return SequenceMatcher(None, x, y).ratio() if x and y else 0.0

    return max(ratio(both, first), ratio(both, second), ratio(first, second))


def craft_aliases(craft: Any) -> list[str]:
    meta = craft.get("extraMetadata") if isinstance(craft, dict) else getattr(craft, "extraMetadata", None)
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except ValueError:
            meta = None
    values = meta.get(ALIASES_KEY) if isinstance(meta, dict) else None
    return [str(v) for v in values or [] if str(v).strip()]


def with_alias(meta: Any, alias: str) -> dict[str, Any]:
    base = dict(meta) if isinstance(meta, dict) else {}
    values = [str(v) for v in base.get(ALIASES_KEY) or []]
    if alias and normalise(alias) not in {normalise(v) for v in values}:
        values.append(alias)
    base[ALIASES_KEY] = values
    return base


def craft_columns(craft: MasterCraft, sub_category_id: str) -> dict[str, Any]:
    return {
        "name": craft.name,
        "subCategoryId": sub_category_id,
        "category": craft.category,
        "sourceSerial": craft.source_serial,
        "stateOfOrigin": list(craft.state_of_origin),
        "stateOfPractice": list(craft.state_of_practice),
        "giStatus": craft.gi_status,
        "isCatchAll": craft.is_catch_all,
        "sourceNotes": list(craft.notes),
    }


def craft_code_for(craft: MasterCraft, codes: SharedCodes | None = None) -> str | None:
    return shared_craft_code(craft.name, codes)


def load_craft_aliases() -> dict[str, Any]:
    if not CRAFT_ALIASES_FILE.exists():
        return {"crafts": {}}
    return _read_json(CRAFT_ALIASES_FILE)


def seed_plan(
    crafts: tuple[MasterCraft, ...] | None = None,
    codes: SharedCodes | None = None,
    aliases: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    crafts = crafts if crafts is not None else load_master()
    codes = codes if codes is not None else shared_codes()
    aliases = aliases if aliases is not None else load_craft_aliases()
    category_rows, sub_rows = _category_rows(categories_of(crafts))
    sub_ids = {row["slug"]: row["id"] for row in sub_rows}
    by_slug = aliases.get("crafts", {}) if isinstance(aliases, dict) else {}
    craft_rows = [_craft_row(craft, codes, sub_ids[craft.sub_category_slug]) for craft in crafts]
    alias_rows = [
        _alias_row(row["id"], alias)
        for craft, row in zip(crafts, craft_rows, strict=True)
        for alias in (by_slug.get(craft.slug) or {}).get("aliases", [])
    ]
    return {
        "categories": category_rows,
        "subCategories": sub_rows,
        "crafts": craft_rows,
        "codes": [{"code": c.code, "name": c.name} for c in codes.crafts],
        "spellings": _spelling_rows(codes),
        "aliases": alias_rows,
    }


def _category_rows(
    categories: tuple[MasterCategory, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    category_rows: list[dict[str, Any]] = []
    sub_rows: list[dict[str, Any]] = []
    for category in categories:
        category_id = seed_uuid("k", category.slug)
        category_rows.append(
            {
                "id": category_id,
                "masterId": master_id("k", category.slug),
                "slug": category.slug,
                "name": category.name,
                "sortOrder": category.sort_order,
            }
        )
        sub_rows += [_sub_row(sub, category_id) for sub in category.sub_categories]
    return category_rows, sub_rows


def _sub_row(sub: MasterSubCategory, category_id: str) -> dict[str, Any]:
    return {
        "id": seed_uuid("s", sub.slug),
        "masterId": master_id("s", sub.slug),
        "slug": sub.slug,
        "name": sub.name,
        "categoryId": category_id,
        "sortOrder": sub.sort_order,
    }


def _spelling_rows(codes: SharedCodes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in codes.crafts:
        for label in (entry.name, *entry.spellings):
            key = codes_normalise(label)
            if key and key not in seen:
                seen.add(key)
                rows.append(
                    {"spelling": key, "label": label, "craftCode": entry.code, "source": SOURCE_SHARED}
                )
    return rows


def _craft_row(craft: MasterCraft, codes: SharedCodes, sub_category_id: str) -> dict[str, Any]:
    wanted = craft_columns(craft, sub_category_id)
    return {
        "id": seed_uuid("c", craft.slug),
        "masterId": master_id("c", craft.slug),
        "slug": craft.slug,
        **wanted,
        "status": ACTIVE,
        "craftCode": craft_code_for(craft, codes),
        "extraMetadata": {MASTER_SEED_KEY: wanted},
    }


def _alias_row(craft_id: str, alias: dict[str, Any]) -> dict[str, Any]:
    return {
        "craftId": craft_id,
        "alias": alias["alias"],
        "aliasNorm": alias["norm"],
        "script": alias.get("script"),
        "lang": alias.get("lang"),
        "source": alias["source"],
        "status": alias.get("status", ACTIVE),
    }


def master_sha1(path: Path = MASTER_FILE) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def recorded_sha1(path: Path = SHA1_FILE) -> str | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text.split()[0] if text else None


def master_is_current() -> bool:
    return recorded_sha1() == master_sha1()
