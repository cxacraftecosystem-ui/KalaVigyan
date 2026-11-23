from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common import read_json, write_json

from app.data.craft_master_loader import (
    ALIASES_FILE,
    CODES_FILE,
    CRAFT_ALIASES_FILE,
    CRAFT_WIKIDATA_FILE,
    MASTER_FILE,
    VOCABULARY_FILE,
    MasterCraft,
    SharedCodes,
    parse_codes,
    parse_master,
)
from app.data.craft_text import alias_norm

from alias_codes import curated_by_slug, map_codes
from alias_entries import (
    CROSS_PORTAL_CODE,
    CURATED,
    IMMERSIVE,
    MASTER,
    TRUST,
    WIKIDATA,
    dedupe,
    entry,
    is_generic,
    name_variants,
)
from alias_scripts import transliterations, vocabulary_tokens
from traditions import IMMERSIVE_ROOT, IMMERSIVE_TO_MASTER

__all__ = ["NameSources", "immersive_alt_names", "main", "merge", "sha1_of", "wikidata_names"]

ABOUT = (
    "Every known name of each master craft, deduplicated by 'norm'. Latin names are folded "
    "(accents removed, lower case, punctuation to single spaces); Indic names keep their script in "
    "'norm' and carry an ASCII 'latin' key. 'source' is the most trusted origin, 'sources' every origin. "
    "PROPOSED rows are machine guesses (fuzzy code mapping, script-to-script transliteration) that the "
    "matcher must not use for an exact hit. A 'norm' listed under 'collisions' names more than one craft "
    "and is never an exact match on its own."
)

Coded = dict[str, list[tuple[str, dict[str, Any]]]]


@dataclass(frozen=True)
class NameSources:
    codes: SharedCodes
    curated: dict[str, list[str]]
    coded: Coded
    wikidata: dict[str, dict[str, Any]]
    immersive: dict[str, list[str]]
    vocabulary: frozenset[str]


def sha1_of(path: Path) -> str | None:
    return hashlib.sha1(path.read_bytes()).hexdigest() if path.exists() else None


def wikidata_names(record: dict[str, Any]) -> list[tuple[str, str]]:
    match = record.get("match") if record.get("status") == "MATCHED" else None
    if not match:
        return []
    out: list[tuple[str, str]] = []
    for lang, label in (match.get("labels") or {}).items():
        out.append((label, lang))
    for lang, values in (match.get("aliases") or {}).items():
        out.extend((value, lang) for value in values)
    enwiki = (match.get("enwiki") or {}).get("title")
    if enwiki:
        out.append((re.sub(r"\s*\([^)]*\)\s*$", "", enwiki), "en"))
    for site, title in (match.get("sitelinks") or {}).items():
        out.append((re.sub(r"\s*\([^)]*\)\s*$", "", title), site.removesuffix("wiki").replace("_", "-")))
    return out


def immersive_alt_names(root: Path = IMMERSIVE_ROOT) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for slug, master in IMMERSIVE_TO_MASTER.items():
        path = root / "traditions" / slug / "tradition.json"
        if not path.exists():
            continue
        data = read_json(path)
        out[master] = [data.get("name", ""), *data.get("alt_names", [])]
    return out


def merge(
    crafts: tuple[MasterCraft, ...],
    codes: SharedCodes,
    curated: dict[str, Any],
    *,
    wikidata: dict[str, Any] | None = None,
    immersive: dict[str, list[str]] | None = None,
    vocabulary: frozenset[str] | None = None,
) -> dict[str, Any]:
    curated_names = curated_by_slug(crafts, curated)
    wd_by_slug = {row["slug"]: row for row in (wikidata or {}).get("crafts", [])}
    known = _known_names(crafts, curated_names, wd_by_slug, immersive or {})
    mapped, ambiguous, unmapped = map_codes(crafts, codes, known)
    coded: Coded = {}
    for code, info in mapped.items():
        coded.setdefault(info["slug"], []).append((code, info))
    sources = NameSources(codes, curated_names, coded, wd_by_slug, immersive or {}, vocabulary or frozenset())
    result = {craft.slug: _craft_names(craft, sources) for craft in crafts}
    aliases = [(slug, alias) for slug, row in result.items() for alias in row["aliases"]]
    return {
        "version": 1,
        "about": ABOUT,
        "trustOrder": sorted(TRUST, key=lambda s: TRUST[s]),
        "summary": dict(sorted(Counter(alias["source"] for _, alias in aliases).items())),
        "codes": {"mapped": dict(sorted(mapped.items())), "ambiguous": ambiguous, "unmapped": sorted(unmapped)},
        "collisions": _collisions(aliases),
        "crafts": result,
    }


def _known_names(
    crafts: tuple[MasterCraft, ...],
    curated_names: dict[str, list[str]],
    wd_by_slug: dict[str, dict[str, Any]],
    immersive: dict[str, list[str]],
) -> dict[str, list[str]]:
    known: dict[str, list[str]] = {}
    for craft in crafts:
        english = [text for text, lang in wikidata_names(wd_by_slug.get(craft.slug, {})) if lang == "en"]
        names = [*curated_names.get(craft.slug, []), *immersive.get(craft.slug, []), *english]
        if names:
            known[craft.slug] = names
    return known


def _craft_names(craft: MasterCraft, sources: NameSources) -> dict[str, Any]:
    found = _named(craft, sources)
    states = (*craft.state_of_practice, *craft.state_of_origin)
    found.extend(transliterations(dedupe(found), states, craft.name, sources.vocabulary))
    return {
        "name": craft.name,
        "craftCodes": sorted(code for code, _ in sources.coded.get(craft.slug, [])),
        "aliases": dedupe(found),
    }


def _named(craft: MasterCraft, sources: NameSources) -> list[dict[str, Any] | None]:
    found: list[dict[str, Any] | None] = []
    for variant in name_variants(craft.name):
        derived = variant != craft.name
        if derived and (craft.is_catch_all or is_generic(alias_norm(variant))):
            continue
        found.append(entry(variant, MASTER, via="derived" if derived else None))
    found.append(entry(craft.slug.replace("-", " "), MASTER, via="slug"))
    found.extend(entry(name, CURATED) for name in sources.curated.get(craft.slug, []))
    for code, info in sources.coded.get(craft.slug, []):
        spec = sources.codes.craft(code)
        for spelling in (spec.name, *spec.spellings) if spec else ():
            found.append(entry(spelling, CROSS_PORTAL_CODE, status=info["status"], via=f"{code} {info['via']}"))
    found.extend(entry(name, IMMERSIVE) for name in sources.immersive.get(craft.slug, []))
    record = sources.wikidata.get(craft.slug, {})
    for text, lang in wikidata_names(record):
        found.append(entry(text, WIKIDATA, lang=lang, via=record["match"]["qid"]))
    return found


def _collisions(aliases: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    owners: dict[str, set[str]] = {}
    for slug, alias in aliases:
        owners.setdefault(alias["norm"], set()).add(slug)
    return [{"norm": norm, "slugs": sorted(slugs)} for norm, slugs in sorted(owners.items()) if len(slugs) > 1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge every craft alias source into craft_aliases.json.")
    parser.add_argument("--output", default=str(CRAFT_ALIASES_FILE))
    parser.add_argument("--immersive-root", default=str(IMMERSIVE_ROOT))
    args = parser.parse_args(argv)
    crafts = parse_master(read_json(MASTER_FILE))
    codes = parse_codes(read_json(CODES_FILE))
    curated = read_json(ALIASES_FILE)
    wikidata = read_json(CRAFT_WIKIDATA_FILE) if CRAFT_WIKIDATA_FILE.exists() else None
    immersive = immersive_alt_names(Path(args.immersive_root)) or _previous_immersive(Path(args.output))
    vocabulary = vocabulary_tokens(VOCABULARY_FILE.read_text(encoding="utf-8"))
    result = merge(crafts, codes, curated, wikidata=wikidata, immersive=immersive, vocabulary=vocabulary)
    result["inputs"] = {
        path.name: sha1_of(path) for path in (MASTER_FILE, CODES_FILE, ALIASES_FILE, CRAFT_WIKIDATA_FILE)
    }
    write_json(Path(args.output), result)
    total = sum(len(row["aliases"]) for row in result["crafts"].values())
    print(
        f"wrote {args.output}: {total} aliases for {len(result['crafts'])} crafts, "
        f"{len(result['codes']['mapped'])} codes mapped, {len(result['codes']['unmapped'])} unmapped, "
        f"{len(result['collisions'])} collisions"
    )
    return 0


def _previous_immersive(output: Path) -> dict[str, list[str]]:
    previous = read_json(output) if output.exists() else {}
    return {
        slug: [a["alias"] for a in row["aliases"] if a["source"] == IMMERSIVE]
        for slug, row in previous.get("crafts", {}).items()
    }


if __name__ == "__main__":
    sys.exit(main())
