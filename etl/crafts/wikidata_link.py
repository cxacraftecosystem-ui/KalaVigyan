from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from common import CACHE_DIR, DATA_DIR, PoliteClient, write_json

from app.data.craft_master_loader import MasterCraft, SharedCodes, load_master, shared_codes
from app.data.craft_text import ascii_key

from wikidata_names import Candidate, clean_term, query_variants
from wikidata_scoring import ACCEPT, CATCH_ALL, FLAG, LOW_CONFIDENCE, MARGIN, MATCHED, decide, is_gi, score
from wikidata_sparql import Linker, parse_coord
from wikidata_vocabulary import GI_INDIA, LANGS

OUTPUT = DATA_DIR / "craft_wikidata.json"
ABOUT = (
    "Wikidata and English Wikipedia matches for the 455 master crafts. MATCHED rows are "
    "confident; LOW_CONFIDENCE rows keep their best guess under 'candidate' and are never used as a "
    "match; NO_MATCH rows list what was considered. Wikidata content is CC0; Wikipedia titles and "
    "categories are CC BY-SA 4.0."
)


@dataclass
class _Found:
    pool: dict[str, Candidate] = field(default_factory=dict)
    per_craft: dict[str, set[str]] = field(default_factory=dict)
    names_for: dict[str, list[str]] = field(default_factory=dict)
    entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    places: dict[str, dict[str, float]] = field(default_factory=dict)
    requests: int = 0
    hits: int = 0


def link(limit: int | None = None, use_cache: bool = True) -> dict[str, Any]:
    crafts = list(load_master())
    if limit:
        crafts = crafts[:limit]
    codes = shared_codes()
    with PoliteClient(cache_dir=CACHE_DIR if use_cache else None) as client:
        found = _found(Linker(client), crafts, codes)
        found.requests = client.requests
        found.hits = client.cache_hits
    records = [_record(craft, found) for craft in crafts]
    resolve_shared(records)
    return _document(records, found)


def describe(
    cand: Candidate, labels: dict[str, str], places: dict[str, dict[str, float]] | None = None
) -> dict[str, Any]:
    gi, gi_cats = is_gi(cand)
    enwiki = cand.sitelinks.get("enwiki")
    commons = cand.claims.get("P373", [])
    images = cand.claims.get("P18", [])
    return {
        "qid": cand.qid,
        "url": f"https://www.wikidata.org/wiki/{cand.qid}",
        "label": cand.labels.get("en"),
        "description": cand.descriptions.get("en"),
        "enwiki": {"title": enwiki, "url": "https://en.wikipedia.org/wiki/" + enwiki.replace(" ", "_")}
        if enwiki
        else None,
        "sitelinks": {site: title for site, title in sorted(cand.sitelinks.items()) if site != "enwiki"},
        "labels": dict(sorted(cand.labels.items())),
        "aliases": {lang: values for lang, values in sorted(cand.aliases.items()) if values},
        "instanceOf": _named(cand.claims.get("P31", []), labels),
        "subclassOf": _named(cand.claims.get("P279", []), labels),
        "country": _named(cand.claims.get("P17", []) + cand.claims.get("P495", []), labels),
        "locatedIn": [
            {"qid": q, "label": labels.get(q), "coordinates": (places or {}).get(q)}
            for q in cand.claims.get("P131", [])
        ],
        "coordinates": _coordinates(cand),
        "commonsCategory": commons[0] if commons else None,
        "image": images[0].rsplit("/", 1)[-1] if images else None,
        "gi": {
            "tagged": gi,
            "wikidataCertification": GI_INDIA in cand.claims.get("P1389", []),
            "wikipediaCategories": gi_cats,
        },
        "wikipediaCategories": cand.enwiki.get("categories", []),
    }


def resolve_shared(records: list[dict[str, Any]]) -> None:
    owners: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        if row["status"] == MATCHED:
            owners.setdefault(row["match"]["qid"], []).append(row)
    for rows in owners.values():
        if len(rows) < 2:
            continue
        rows.sort(key=lambda r: -r["confidence"])
        clear = rows[0]["confidence"] - rows[1]["confidence"] >= MARGIN
        for row in rows[1:] if clear else rows:
            row["status"] = LOW_CONFIDENCE
            row["candidate"] = row["match"]
            row["match"] = None
            row["reasons"] = [*row.get("reasons", []), "item shared with another craft"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Link master crafts to Wikidata and Wikipedia.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args(argv)
    result = link(limit=args.limit, use_cache=not args.no_cache)
    write_json(Path(args.output), result)
    print(f"wrote {args.output}: {result['summary']}, requests {result['requests']}")
    return 0


def _found(linker: Linker, crafts: list[MasterCraft], codes: SharedCodes) -> _Found:
    found = _Found()
    gi_choices = {qid: ascii_key(label) for qid, label in linker.gi_pool().items()}
    for craft in crafts:
        if craft.is_catch_all:
            continue
        code = codes.spelling_index.get(ascii_key(craft.name))
        extra = list(codes.craft(code).spellings[:3]) if code and codes.craft(code) else []
        variants = query_variants(craft, extra)
        found.names_for[craft.slug] = variants
        found.per_craft[craft.slug] = _gi_pool_matches(variants, gi_choices, found.pool)
    _search(linker, found)
    _fill_entities(linker, found)
    _fill_claims_and_pages(linker, found)
    return found


def _gi_pool_matches(variants: list[str], gi_choices: dict[str, str], pool: dict[str, Candidate]) -> set[str]:
    from rapidfuzz import fuzz, process

    qids: set[str] = set()
    for text in variants[:3]:
        for _, sim, qid in process.extract(ascii_key(text), gi_choices, scorer=fuzz.token_sort_ratio, limit=2):
            if sim >= 80:
                qids.add(qid)
                pool.setdefault(qid, Candidate(qid)).found_by.add("gi-pool")
    return qids


def _search(linker: Linker, found: _Found) -> None:
    client = linker.client
    wiki_terms = sorted({clean_term(t) for v in found.names_for.values() for t in v[:3]})
    wd_terms = sorted({clean_term(t) for v in found.names_for.values() for t in v[:2]})
    print(f"searching {len(wiki_terms)} Wikipedia and {len(wd_terms)} Wikidata terms", flush=True)
    wiki_hits = linker.wikipedia_search(wiki_terms)
    print(f"wikipedia search done, {client.requests} requests", flush=True)
    wd_hits = linker.wikidata_search(wd_terms)
    print(f"wikidata search done, {client.requests} requests", flush=True)
    for slug, variants in found.names_for.items():
        for text in variants[:3]:
            _add_hits(found, slug, wiki_hits.get(clean_term(text), []), "enwiki-search")
        for text in variants[:2]:
            _add_hits(found, slug, wd_hits.get(clean_term(text), []), "wikidata-search")


def _add_hits(found: _Found, slug: str, qids: list[str], source: str) -> None:
    for qid in qids:
        found.per_craft[slug].add(qid)
        found.pool.setdefault(qid, Candidate(qid)).found_by.add(source)


def _fill_entities(linker: Linker, found: _Found) -> None:
    found.entities = linker.entities(list(found.pool))
    print(f"entities done, {linker.client.requests} requests", flush=True)
    for qid, entity in found.entities.items():
        cand = found.pool.setdefault(qid, Candidate(qid))
        cand.labels = {k: v["value"] for k, v in entity.get("labels", {}).items()}
        cand.aliases = {k: [a["value"] for a in v] for k, v in entity.get("aliases", {}).items()}
        cand.descriptions = {k: v["value"] for k, v in entity.get("descriptions", {}).items()}
        cand.sitelinks = {k: v["title"] for k, v in entity.get("sitelinks", {}).items()}


def _fill_claims_and_pages(linker: Linker, found: _Found) -> None:
    pool = found.pool
    for qid, props in linker.claims(list(pool)).items():
        if qid in pool:
            pool[qid].claims = props
    referenced = {
        v for cand in pool.values() for p in ("P31", "P279", "P17", "P495", "P131") for v in cand.claims.get(p, [])
    }
    found.labels = linker.labels(sorted(referenced))
    found.places = linker.coordinates(sorted({v for cand in pool.values() for v in cand.claims.get("P131", [])}))
    titles = [c.sitelinks["enwiki"] for c in pool.values() if c.sitelinks.get("enwiki")]
    pages = linker.enwiki_pages(titles)
    for cand in pool.values():
        title = cand.sitelinks.get("enwiki")
        if title and title in pages:
            cand.enwiki = pages[title]


def _record(craft: MasterCraft, found: _Found) -> dict[str, Any]:
    base = {
        "slug": craft.slug,
        "name": craft.name,
        "sourceSerial": craft.source_serial,
        "subCategorySlug": craft.sub_category_slug,
        "masterGiStatus": craft.gi_status,
    }
    if craft.is_catch_all:
        return {**base, "status": CATCH_ALL, "confidence": None, "match": None, "candidate": None, "candidates": []}
    ranked = _ranked(craft, found)
    status = decide(ranked)
    top = ranked[0] if ranked else None
    return {
        **base,
        "status": status,
        "confidence": top[0] if top else None,
        "reasons": top[2] if top else [],
        "match": describe(top[1], found.labels, found.places) if top and status == MATCHED else None,
        "candidate": describe(top[1], found.labels, found.places) if top and status == LOW_CONFIDENCE else None,
        "candidates": [_listed(conf, cand) for conf, cand, _ in ranked[:3]],
    }


def _ranked(craft: MasterCraft, found: _Found) -> list[tuple[float, Candidate, list[str]]]:
    pool = found.pool
    ranked = sorted(
        (
            (*score(craft, found.names_for[craft.slug], pool[q], found.labels), pool[q])
            for q in found.per_craft.get(craft.slug, set())
            if q in found.entities
        ),
        key=lambda row: (-row[0], row[2].qid),
    )
    return [(conf, cand, reasons) for conf, reasons, cand in ranked]


def _listed(conf: float, cand: Candidate) -> dict[str, Any]:
    return {
        "qid": cand.qid,
        "label": cand.labels.get("en"),
        "description": cand.descriptions.get("en"),
        "confidence": conf,
        "foundBy": sorted(cand.found_by),
    }


def _document(records: list[dict[str, Any]], found: _Found) -> dict[str, Any]:
    summary: dict[str, int] = {}
    for row in records:
        summary[row["status"]] = summary.get(row["status"], 0) + 1
    gi_disagree = [
        row["slug"]
        for row in records
        if row["match"] and row["masterGiStatus"] == "GI" and not row["match"]["gi"]["tagged"]
    ]
    return {
        "version": 1,
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "about": ABOUT,
        "thresholds": {"accept": ACCEPT, "flag": FLAG, "margin": MARGIN},
        "languages": list(LANGS),
        "summary": dict(sorted(summary.items())),
        "requests": {"network": found.requests, "cache": found.hits},
        "masterGiNotTaggedOnWikidata": gi_disagree,
        "crafts": records,
    }


def _named(qids: list[str], labels: dict[str, str]) -> list[dict[str, Any]]:
    return [{"qid": q, "label": labels.get(q)} for q in qids]


def _coordinates(cand: Candidate) -> list[dict[str, float]]:
    coords = [c for c in (parse_coord(v) for v in cand.claims.get("P625", [])) if c]
    for c in cand.enwiki.get("coordinates", []):
        point = {"lat": round(c["lat"], 6), "lon": round(c["lon"], 6)}
        if point not in coords:
            coords.append(point)
    return coords


if __name__ == "__main__":
    sys.exit(main())
