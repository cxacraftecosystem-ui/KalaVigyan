from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from app.data.craft_text import SCRIPT_LANG, alias_norm, ascii_key, script_of

__all__ = [
    "ACTIVE",
    "CROSS_PORTAL_CODE",
    "CURATED",
    "GENERIC_WORDS",
    "IMMERSIVE",
    "MASTER",
    "PROPOSED",
    "TRANSLITERATION",
    "TRUST",
    "WIKIDATA",
    "dedupe",
    "entry",
    "is_generic",
    "name_variants",
]

ACTIVE = "ACTIVE"
PROPOSED = "PROPOSED"

MASTER = "MASTER"
CURATED = "CURATED"
CROSS_PORTAL_CODE = "CROSS_PORTAL_CODE"
IMMERSIVE = "IMMERSIVE"
WIKIDATA = "WIKIDATA"
TRANSLITERATION = "TRANSLITERATION"

TRUST = {MASTER: 0, CURATED: 1, CROSS_PORTAL_CODE: 2, IMMERSIVE: 3, WIKIDATA: 4, TRANSLITERATION: 5}

GENERIC_WORDS = frozenset(
    {
        "embroidery",
        "work",
        "works",
        "craft",
        "crafts",
        "art",
        "arts",
        "painting",
        "paintings",
        "pottery",
        "print",
        "prints",
        "printing",
        "hand",
        "block",
        "carving",
        "carvings",
        "weaving",
        "textile",
        "textiles",
        "metal",
        "ware",
        "wares",
        "product",
        "products",
        "of",
        "the",
        "and",
        "india",
        "indian",
        "traditional",
        "folk",
        "wood",
        "wooden",
        "stone",
        "toy",
        "toys",
        "doll",
        "dolls",
        "jewellery",
        "jewelry",
        "bamboo",
        "cane",
        "brass",
        "bronze",
        "copper",
        "silver",
        "gold",
        "iron",
        "leather",
        "glass",
        "paper",
        "applique",
        "saree",
        "sari",
        "shawl",
        "terracotta",
        "clay",
        "handicraft",
        "handicrafts",
        "textile art",
        "dyeing",
        "dye",
        "resist",
        "cloth",
        "fabric",
        "lamp",
        "mat",
        "mats",
        "basket",
        "baskets",
        "musical",
        "instrument",
        "instruments",
        "drum",
        "jewel",
        "beads",
        "bead",
        "other",
        "others",
        "style",
        "technique",
        "indigo",
        "alizarin",
        "flower",
        "flowers",
        "gum",
    }
)

STATE_SUFFIX = re.compile(r"\s+of\s+[A-Z][A-Za-z ]+$")


def is_generic(norm: str) -> bool:
    tokens = norm.split()
    return not tokens or all(t in GENERIC_WORDS for t in tokens)


def entry(
    alias: str,
    source: str,
    *,
    lang: str | None = None,
    status: str = ACTIVE,
    via: str | None = None,
) -> dict[str, Any] | None:
    alias = " ".join(str(alias or "").split())
    if not alias:
        return None
    script = script_of(alias)
    norm = alias_norm(alias)
    if not norm or (source != MASTER and is_generic(ascii_key(alias) if script != "Latn" else norm)):
        return None
    if script in ("Latn", "Zyyy") and len(norm.replace(" ", "")) < 3:
        return None
    latin = ascii_key(alias)
    return {
        "alias": alias,
        "norm": norm,
        "latin": latin,
        "script": script,
        "lang": lang or ("en" if script == "Latn" else SCRIPT_LANG.get(script)),
        "source": source,
        "status": status,
        "via": via,
    }


def name_variants(name: str) -> list[str]:
    out = [name]
    outer = re.sub(r"\s*\([^)]*\)\s*", " ", name).strip()
    out.append(outer)
    out.extend(part.strip(" \"'“”") for part in re.findall(r"\(([^)]*)\)", name))
    out.append(STATE_SUFFIX.sub("", outer))
    seen: set[str] = set()
    result: list[str] = []
    for value in out:
        key = ascii_key(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def dedupe(entries: Iterable[dict[str, Any] | None]) -> list[dict[str, Any]]:
    by_norm: dict[str, dict[str, Any]] = {}
    for item in entries:
        if not item:
            continue
        current = by_norm.get(item["norm"])
        if current is None:
            by_norm[item["norm"]] = {**item, "sources": [item["source"]]}
            continue
        sources = sorted(set(current["sources"]) | {item["source"]}, key=lambda s: TRUST[s])
        better = TRUST[item["source"]] < TRUST[current["source"]]
        status = ACTIVE if ACTIVE in (current["status"], item["status"]) else current["status"]
        base = {**item} if better else current
        by_norm[item["norm"]] = {**base, "sources": sources, "status": status}
    return sorted(by_norm.values(), key=lambda a: (TRUST[a["source"]], a["script"] != "Latn", a["norm"]))
