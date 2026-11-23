from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.data.craft_master_loader import MasterCraft, SharedCodes, codes_normalise
from app.data.craft_text import ascii_key

from alias_entries import ACTIVE, PROPOSED, is_generic, name_variants

__all__ = ["FUZZY_LEAD_MIN", "FUZZY_SCORE_MIN", "curated_by_slug", "map_codes"]

FUZZY_SCORE_MIN = 90
FUZZY_LEAD_MIN = 5

CodeMapping = tuple[dict[str, dict[str, Any]], dict[str, list[str]], list[str]]


def curated_by_slug(crafts: tuple[MasterCraft, ...], curated: dict[str, Any]) -> dict[str, list[str]]:
    by_serial = {c.source_serial: c.slug for c in crafts}
    decisions = {codes_normalise(row["oldName"]): row for row in curated.get("crafts", [])}
    out: dict[str, list[str]] = {}
    for row in curated.get("crafts", []):
        slug = by_serial.get(row.get("sourceSerial"))
        if slug:
            out.setdefault(slug, []).append(row["oldName"])
    for row in curated.get("freeText", []):
        target = decisions.get(codes_normalise(row.get("sameAs")))
        slug = by_serial.get(target.get("sourceSerial")) if target else None
        if slug:
            out.setdefault(slug, []).append(row["text"])
    return out


def map_codes(crafts: tuple[MasterCraft, ...], codes: SharedCodes, known: dict[str, list[str]]) -> CodeMapping:
    index = _code_index(crafts, known)
    choices = {c.slug: ascii_key(c.name) for c in crafts if not c.is_catch_all}
    mapped: dict[str, dict[str, Any]] = {}
    ambiguous: dict[str, list[str]] = {}
    unmapped: list[str] = []
    for code in codes.crafts:
        spellings = (code.name, *code.spellings)
        hits = set().union(*(index.get(codes_normalise(spelling), set()) for spelling in spellings))
        if len(hits) == 1:
            mapped[code.code] = {"slug": next(iter(hits)), "via": "exact", "status": ACTIVE}
        elif len(hits) > 1:
            ambiguous[code.code] = sorted(hits)
        elif (fuzzy := _fuzzy_match(spellings, choices)) is not None:
            mapped[code.code] = fuzzy
        else:
            unmapped.append(code.code)
    return mapped, ambiguous, unmapped


def _code_index(crafts: tuple[MasterCraft, ...], known: dict[str, list[str]]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for craft in crafts:
        if craft.is_catch_all:
            continue
        for variant in name_variants(craft.name):
            index.setdefault(codes_normalise(variant), set()).add(craft.slug)
    for slug, names in known.items():
        for name in names:
            key = codes_normalise(name)
            if key and not is_generic(key):
                index.setdefault(key, set()).add(slug)
    return index


def _fuzzy_match(spellings: Sequence[str], choices: dict[str, str]) -> dict[str, Any] | None:
    from rapidfuzz import fuzz, process

    best: list[tuple[str, float, str]] = []
    for spelling in spellings:
        best.extend(process.extract(ascii_key(spelling), choices, scorer=fuzz.token_sort_ratio, limit=2))
    best.sort(key=lambda row: -row[1])
    if not best or best[0][1] < FUZZY_SCORE_MIN:
        return None
    rivals = [row for row in best if row[2] != best[0][2]]
    if rivals and best[0][1] - rivals[0][1] < FUZZY_LEAD_MIN:
        return None
    return {"slug": best[0][2], "via": f"fuzzy {best[0][1]:.0f}", "status": PROPOSED}
