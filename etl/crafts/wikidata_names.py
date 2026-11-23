from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.data.craft_master_loader import MasterCraft
from app.data.craft_text import STOP_TOKENS, ascii_key, to_latin_spoken

from wikidata_vocabulary import INDIAN_STATES

__all__ = [
    "GENERIC",
    "Candidate",
    "candidate_names",
    "clean_term",
    "distinctive",
    "name_similarity",
    "query_variants",
    "shares_distinctive",
    "strip_disambiguation",
]

GENERIC = frozenset(
    {
        "embroidery",
        "embroidered",
        "work",
        "works",
        "craft",
        "crafts",
        "art",
        "arts",
        "painting",
        "paintings",
        "pottery",
        "potteries",
        "print",
        "prints",
        "printing",
        "printed",
        "hand",
        "handmade",
        "block",
        "carving",
        "carvings",
        "carved",
        "weaving",
        "woven",
        "weave",
        "textile",
        "textiles",
        "metal",
        "metalware",
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
        "sarees",
        "shawl",
        "shawls",
        "craftwork",
        "kala",
        "items",
        "articles",
        "making",
        "industry",
        "style",
        "design",
        "designs",
        "terracotta",
        "clay",
    }
)


def distinctive(tokens: Iterable[str]) -> set[str]:
    return {t for t in tokens if t not in GENERIC and len(t) > 2}


def shares_distinctive(craft_names: Iterable[str], candidate: Iterable[str]) -> bool | None:
    from rapidfuzz import fuzz

    wanted: set[str] = set()
    for name in craft_names:
        wanted |= distinctive(ascii_key(name).split())
    if not wanted:
        return None
    have: set[str] = set()
    for name in candidate:
        have |= set(ascii_key(name).split())
    return any(fuzz.ratio(w, h) >= 85 for w in wanted for h in have)


@dataclass
class Candidate:
    qid: str
    found_by: set[str] = field(default_factory=set)
    labels: dict[str, str] = field(default_factory=dict)
    aliases: dict[str, list[str]] = field(default_factory=dict)
    descriptions: dict[str, str] = field(default_factory=dict)
    sitelinks: dict[str, str] = field(default_factory=dict)
    claims: dict[str, list[Any]] = field(default_factory=dict)
    enwiki: dict[str, Any] = field(default_factory=dict)


def clean_term(text: str) -> str:
    return " ".join(re.sub(r"[\\\"\n\r\t]", " ", text).split())


def query_variants(craft: MasterCraft, extra: Iterable[str] = ()) -> list[str]:
    name = craft.name
    out: list[str] = [name]
    inner = re.findall(r"\(([^)]*)\)", name)
    outer = re.sub(r"\s*\([^)]*\)\s*", " ", name).strip()
    out.append(outer)
    out.extend(part.strip(" \"'“”") for part in inner)
    stripped = re.sub(r"\s+of\s+(" + "|".join(re.escape(s) for s in INDIAN_STATES) + r")$", "", outer, flags=re.I)
    out.append(stripped)
    out.extend(extra)
    seen: set[str] = set()
    result: list[str] = []
    for value in out:
        key = ascii_key(value)
        if key and key not in seen and len(key) > 2:
            seen.add(key)
            result.append(value.strip())
    return result


def _tokens(text: str) -> list[str]:
    return [t for t in ascii_key(text).split() if t not in STOP_TOKENS] or ascii_key(text).split()


def name_similarity(craft_names: Iterable[str], candidate_names: Iterable[str]) -> float:
    from rapidfuzz import fuzz

    best = 0.0
    craft_list = [n for n in craft_names if ascii_key(n)]
    for cand in candidate_names:
        ct = _tokens(cand)
        if not ct:
            continue
        cand_key = " ".join(ct)
        for name in craft_list:
            nt = _tokens(name)
            if not nt:
                continue
            name_key = " ".join(nt)
            cand_cover = sum(max(fuzz.ratio(t, u) for u in nt) for t in ct) / len(ct)
            craft_cover = sum(max(fuzz.ratio(u, t) for t in ct) for u in nt) / len(nt)
            tok = 0.6 * cand_cover + 0.4 * craft_cover
            whole = max(fuzz.ratio(name_key, cand_key), fuzz.token_sort_ratio(name_key, cand_key))
            best = max(best, tok / 100, whole / 100)
    return round(min(best, 1.0), 4)


def strip_disambiguation(title: str) -> tuple[str, str | None]:
    match = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", title)
    return (match.group(1), match.group(2)) if match else (title, None)


def candidate_names(cand: Candidate) -> list[str]:
    names: list[str] = []
    if "en" in cand.labels:
        names.append(cand.labels["en"])
    names.extend(cand.aliases.get("en", []))
    if cand.sitelinks.get("enwiki"):
        names.append(strip_disambiguation(cand.sitelinks["enwiki"])[0])
    if not names:
        for lang, label in cand.labels.items():
            if lang != "en":
                names.append(to_latin_spoken(label))
    return names
