from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

from common import read_json, write_json

from app.data.craft_master_loader import MASTER_FILE, SEED_CLAIMS_FILE, parse_master
from source_authors import split_authors

from traditions import (
    IMMERSIVE_ROOT,
    IMMERSIVE_TO_MASTER,
    INFERENTIAL_ROOT,
    INFERENTIAL_TO_SUB_CATEGORY,
    SHARED_SCIENCE_SUB_CATEGORY,
)

QUOTE_MAX = 300

PROVISIONAL = "PROVISIONAL"
HYPOTHESIS = "HYPOTHESIS"

CONCEPT_TYPES = {
    "tradition": "TRADITION",
    "material": "MATERIAL",
    "tool": "TOOL",
    "process_stage": "PROCESS_STAGE",
    "artisan_decision": "ARTISAN_DECISION",
    "design_principle": "DESIGN_PRINCIPLE",
    "outcome": "OUTCOME",
    "scientific_mechanism": "MECHANISM",
    "mechanism": "MECHANISM",
    "environmental_condition": "ENVIRONMENTAL_CONDITION",
    "environment": "ENVIRONMENTAL_CONDITION",
    "historical_context": "HISTORICAL_CONTEXT",
    "history": "HISTORICAL_CONTEXT",
    "comparison": "COMPARISON",
    "explanation": "EXPLANATION",
    "open_question": "OPEN_QUESTION",
    "action": "ARTISAN_ACTION",
    "sensory_cue": "SENSORY_CUE",
    "property": "PROPERTY",
    "change": "CHANGE",
    "concept": "CONCEPT",
}

RELATIONS = {
    "BELONGS_TO": "PART_OF",
    "PART_OF": "PART_OF",
    "USES": "USES",
    "PRECEDES": "PRECEDES",
    "PRODUCES": "PRODUCES",
    "AFFECTED_BY": "AFFECTED_BY",
    "SCIENTIFICALLY_EXPLAINED_BY": "SCIENTIFICALLY_EXPLAINED_BY",
}

STAGE_TYPES: tuple[tuple[str, str], ...] = (
    ("scour", "SCOUR"),
    ("saaj", "SCOUR"),
    ("desiz", "SCOUR"),
    ("mordant", "MORDANT"),
    ("harda", "MORDANT"),
    ("tannin", "MORDANT"),
    ("resist", "RESIST"),
    ("dabu", "RESIST"),
    ("mud", "RESIST"),
    ("indigo", "DYE"),
    ("dye", "DYE"),
    ("dyeing", "DYE"),
    ("boil", "DYE"),
    ("print", "PRINT"),
    ("wash", "WASH"),
    ("rins", "WASH"),
    ("dry", "DRY"),
    ("sun", "DRY"),
    ("bleach", "DRY"),
    ("fir", "FIRE"),
    ("kiln", "FIRE"),
    ("cast", "CAST"),
    ("carv", "CARVE"),
    ("shap", "SHAPE"),
    ("form", "SHAPE"),
    ("finish", "FINISH"),
    ("burnish", "FINISH"),
)

RELIABILITY = {"high": "A", "medium": "B", "low": "C"}

EVIDENCE_RELATION = {
    "analogous": "ANALOGOUS",
    "general_principle": "GENERAL_PRINCIPLE",
    "contextual": "CONTEXTUAL",
    "derived": "CONTEXTUAL",
}


def sha1_text(*parts: str) -> str:
    return hashlib.sha1("␟".join(parts).encode("utf-8")).hexdigest()


def clip_quote(quote: str) -> tuple[str, bool]:
    quote = " ".join(str(quote or "").split())
    if len(quote) <= QUOTE_MAX:
        return quote, False
    cut = quote[:QUOTE_MAX]
    space = cut.rfind(" ")
    return (cut[:space] if space > QUOTE_MAX // 2 else cut).rstrip(" ,;:"), True


def stage_type(*texts: str) -> str:
    blob = " ".join(texts).lower()
    for needle, kind in STAGE_TYPES:
        if re.search(r"(?<![a-z])" + re.escape(needle), blob):
            return kind
    return "OTHER"


def publication_kind(src: dict[str, Any]) -> str:
    title = str(src.get("title") or "").lower()
    publisher = str(src.get("publisher") or "").lower()
    url = str(src.get("url") or "").lower()
    blob = f"{title} {publisher} {url}"
    if "geographical indication" in blob or "ipindia" in url:
        return "GI_JOURNAL"
    if "doi.org" in url or "journal" in publisher or "proceedings" in publisher or "thesis" in title:
        return "PAPER"
    if ".gov" in url or ".nic.in" in url or "ministry" in blob or "government" in blob or "census" in blob:
        return "GOVERNMENT_REPORT"
    if "wikipedia.org" in url:
        return "ENCYCLOPEDIA"
    if url.endswith(".pdf"):
        return "PAPER" if "university" in blob or "research" in blob else "WEB_PAGE"
    return "WEB_PAGE" if url else "OTHER"


def citation_kind(source_type: str, citation: str) -> str:
    if source_type == "scientific_literature":
        return "PAPER" if re.search(r"\bjournal\b|\d+\(\d+\)|doi", citation, re.I) else "BOOK"
    return "OTHER"


def immersive_source(file_slug: str, src: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"ie:{file_slug}:{src['id']}",
        "kind": publication_kind(src),
        "evidenceKind": str(src.get("kind", "")).upper() or None,
        "title": src.get("title"),
        "authors": split_authors(src.get("author")),
        "year": src.get("year"),
        "doi": None,
        "url": src.get("url"),
        "publisher": src.get("publisher"),
        "licence": None,
        "reliability": RELIABILITY.get(str(src.get("reliability", "")).lower(), "D"),
        "storage": "EXCERPT",
        "retrievedAt": src.get("accessed"),
        "origin": "IMPORT",
        "sensitivity": "OPEN",
        "notes": src.get("notes"),
        "importRef": {"repo": "immersive-episteme", "file": file_slug, "id": src["id"]},
    }


def stage_ordinals(data: dict[str, Any]) -> dict[str, int]:
    types = {c["key"]: c["type"] for c in data.get("concepts", [])}
    ordinals: dict[str, int] = {}
    for rel in data.get("relationships", []):
        if rel.get("type") != "PRECEDES" or rel.get("ordinal") is None:
            continue
        if types.get(rel["source"]) != "process_stage" or types.get(rel["target"]) != "process_stage":
            continue
        ordinals.setdefault(rel["source"], int(rel["ordinal"]))
        ordinals[rel["target"]] = max(ordinals.get(rel["target"], 0), int(rel["ordinal"]) + 1)
    return ordinals


def evidence_rows(file_slug: str, items: list[dict[str, Any]], checked: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        quote, clipped = clip_quote(item.get("quote", ""))
        if not quote:
            continue
        rows.append(
            {
                "sourceId": f"ie:{file_slug}:{item['source_id']}",
                "locator": item.get("locator"),
                "quote": quote,
                "quoteClipped": clipped,
                "quoteCheck": "PASS" if checked and not item.get("note") else "NA",
                "relation": "DIRECT",
                "note": item.get("note"),
            }
        )
    return rows


def level_for(provenance: str | None, sources: list[dict[str, Any]]) -> tuple[str, str]:
    if not sources:
        return HYPOTHESIS, "no quoted passage"
    if provenance in ("hypothesis", "unverified"):
        return HYPOTHESIS, f"source states it as {provenance}"
    if any(s["quoteCheck"] == "PASS" for s in sources):
        return PROVISIONAL, "quote re-found verbatim by the immersive-episteme source check"
    return HYPOTHESIS, "quote not mechanically checked"


def convert_immersive(data: dict[str, Any], file_slug: str, craft_slug: str | None, sub_slug: str) -> dict[str, Any]:
    sources = [immersive_source(file_slug, s) for s in data.get("sources", [])]
    ordinals = stage_ordinals(data)
    concepts: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    titles = {c["key"]: c["title"] for c in data.get("concepts", [])}
    for concept in data.get("concepts", []):
        key = f"ie:{concept['key']}"
        is_stage = concept["type"] == "process_stage"
        stage = (
            {
                "key": key,
                "title": concept["title"],
                "ordinal": ordinals.get(concept["key"]),
                "stageType": stage_type(concept["title"], concept.get("summary", "")),
            }
            if is_stage
            else None
        )
        concepts.append(
            {
                "key": key,
                "craftSlug": craft_slug,
                "subCategorySlug": sub_slug,
                "type": CONCEPT_TYPES.get(concept["type"], concept["type"].upper()),
                "category": concept.get("category"),
                "name": concept["title"],
                "description": concept.get("summary"),
                "localTerms": concept.get("local_terms", []),
                "provenanceKind": concept.get("provenance_kind"),
                "stage": stage,
                "compares": [f"ie:{k}" for k in concept.get("compares", [])],
            }
        )
        checked = concept.get("verification_state") == "verified"
        for index, claim in enumerate(concept.get("claims", [])):
            rows = evidence_rows(file_slug, claim.get("evidence", []), checked)
            level, reason = level_for(concept.get("provenance_kind"), rows)
            claims.append(
                {
                    "id": "seed-" + sha1_text(key, claim["text"])[:20],
                    "craftSlug": craft_slug,
                    "subCategorySlug": sub_slug,
                    "subjectType": "CONCEPT",
                    "subjectKey": key,
                    "subjectName": concept["title"],
                    "predicate": CONCEPT_TYPES.get(concept["type"], concept["type"].upper()),
                    "text": claim["text"],
                    "textLang": "en",
                    "stage": stage,
                    "evidenceLevel": level,
                    "levelReason": reason,
                    "provenanceKind": concept.get("provenance_kind"),
                    "origin": "IMPORT",
                    "status": "PROPOSED",
                    "createdByKind": "SYSTEM",
                    "systemActor": "import",
                    "sensitivity": "OPEN",
                    "sources": rows,
                    "importRef": {
                        "repo": "immersive-episteme",
                        "file": file_slug,
                        "key": concept["key"],
                        "claim": index,
                    },
                }
            )
    for rel in data.get("relationships", []):
        relation = RELATIONS.get(rel["type"], rel["type"])
        edge_key = f"ie:{rel['source']}|{rel['type']}|{rel['target']}"
        edges.append(
            {
                "key": edge_key,
                "src": f"ie:{rel['source']}",
                "dst": f"ie:{rel['target']}",
                "relation": relation,
                "sourceRelation": rel["type"],
                "ordinal": rel.get("ordinal"),
                "conditions": rel.get("conditions"),
            }
        )
        if rel["type"] == "BELONGS_TO" or not rel.get("explanation"):
            continue
        checked = rel.get("verification_state") == "verified"
        rows = evidence_rows(file_slug, rel.get("evidence", []), checked)
        level, reason = level_for(rel.get("provenance_kind"), rows)
        stage_key = rel["source"] if titles.get(rel["source"]) and ordinals.get(rel["source"]) else None
        claims.append(
            {
                "id": "seed-" + sha1_text(edge_key, rel["explanation"])[:20],
                "craftSlug": craft_slug,
                "subCategorySlug": sub_slug,
                "subjectType": "EDGE",
                "subjectKey": edge_key,
                "subjectName": f"{titles.get(rel['source'], rel['source'])} → {titles.get(rel['target'], rel['target'])}",
                "predicate": relation,
                "text": rel["explanation"],
                "textLang": "en",
                "stage": {"key": f"ie:{stage_key}", "title": titles[stage_key], "ordinal": ordinals[stage_key]}
                if stage_key
                else None,
                "evidenceLevel": level,
                "levelReason": reason,
                "provenanceKind": rel.get("provenance_kind"),
                "origin": "IMPORT",
                "status": "PROPOSED",
                "createdByKind": "SYSTEM",
                "systemActor": "import",
                "sensitivity": "OPEN",
                "sources": rows,
                "importRef": {"repo": "immersive-episteme", "file": file_slug, "relationship": edge_key[3:]},
            }
        )
    region = data.get("region") or None
    gi = data.get("gi") or None
    return {
        "tradition": {
            "file": file_slug,
            "craftSlug": craft_slug,
            "subCategorySlug": sub_slug,
            "name": data.get("name"),
            "altNames": data.get("alt_names", []),
            "summary": data.get("summary"),
            "region": region,
            "gi": {**gi, "sourceIds": [f"ie:{file_slug}:{s}" for s in gi.get("source_ids", [])]} if gi else None,
        },
        "sources": sources,
        "concepts": concepts,
        "edges": edges,
        "claims": claims,
    }


def inferential_sources(domain: str, data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}

    def add(source_type: str, citation: str) -> str:
        sid = "inf:" + sha1_text(citation)[:12]
        if sid not in out:
            programme = source_type == "expert_interpretation"
            out[sid] = {
                "id": sid,
                "kind": citation_kind(source_type, citation),
                "evidenceKind": source_type.upper(),
                "title": citation,
                "authors": [],
                "year": None,
                "doi": None,
                "url": None,
                "publisher": None,
                "licence": None,
                "reliability": "D" if programme or source_type == "other" else "C",
                "storage": "LINK_ONLY",
                "retrievedAt": None,
                "origin": "IMPORT",
                "sensitivity": "OPEN",
                "notes": "Citation from an inferential-system draft seed; not fetched or quote-checked.",
                "importRef": {"repo": "inferential-system", "file": domain},
            }
        return sid

    for row in data.get("nodes", []) + data.get("edges", []):
        for prov in row.get("provenance", []):
            add(prov.get("source_type", "other"), prov.get("citation", ""))
    for item in data.get("evidence", []):
        add(item.get("source_type", "other"), item.get("citation", ""))
    return out


def convert_inferential(data: dict[str, Any], domain: str, sub_slug: str) -> dict[str, Any]:
    sources = inferential_sources(domain, data)
    by_citation = {s["title"]: sid for sid, s in sources.items()}
    concepts: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    labels = {n["key"]: n["label"] for n in data.get("nodes", [])}

    def cite(provenance: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "sourceId": by_citation[p.get("citation", "")],
                "locator": p.get("detail"),
                "quote": None,
                "quoteClipped": False,
                "quoteCheck": "NA",
                "relation": "GENERAL_PRINCIPLE" if p.get("source_type") == "scientific_literature" else "CONTEXTUAL",
                "note": None,
            }
            for p in provenance
        ]

    def claim(
        subject_type: str,
        key: str,
        name: str,
        predicate: str,
        text: str,
        rows: list[dict[str, Any]],
        reason: str,
        ref: dict[str, Any],
        related: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": "seed-" + sha1_text(key, text)[:20],
            "craftSlug": None,
            "subCategorySlug": sub_slug,
            "subjectType": subject_type,
            "subjectKey": key,
            "subjectName": name,
            "predicate": predicate,
            "text": text,
            "textLang": "en",
            "stage": None,
            "evidenceLevel": HYPOTHESIS,
            "levelReason": reason,
            "provenanceKind": None,
            "origin": "IMPORT",
            "status": "PROPOSED",
            "createdByKind": "SYSTEM",
            "systemActor": "import",
            "sensitivity": "OPEN",
            "sources": rows,
            "relatedKeys": related or [],
            "importRef": {"repo": "inferential-system", "file": domain, **ref},
        }

    draft_reason = "draft seed: textbook citation without a checked quote"
    for node in data.get("nodes", []):
        key = f"inf:{domain}:{node['key']}"
        kind = CONCEPT_TYPES.get(node["node_type"], node["node_type"].upper())
        concepts.append(
            {
                "key": key,
                "craftSlug": None,
                "subCategorySlug": sub_slug,
                "type": kind,
                "category": node.get("knowledge_domain"),
                "name": node["label"],
                "description": node.get("statement"),
                "localTerms": node.get("aliases", []),
                "provenanceKind": None,
                "stage": {"key": key, "title": node["label"], "ordinal": None, "stageType": stage_type(node["label"])}
                if node["node_type"] == "process_stage"
                else None,
                "compares": [],
            }
        )
        claims.append(
            claim(
                "CONCEPT",
                key,
                node["label"],
                kind,
                node["statement"],
                cite(node.get("provenance", [])),
                draft_reason,
                {"node": node["key"]},
            )
        )
    for edge in data.get("edges", []):
        relation = edge["relation"].upper()
        key = f"inf:{domain}:{edge['source']}|{relation}|{edge['target']}"
        edges.append(
            {
                "key": key,
                "src": f"inf:{domain}:{edge['source']}",
                "dst": f"inf:{domain}:{edge['target']}",
                "relation": RELATIONS.get(relation, relation),
                "sourceRelation": edge["relation"],
                "ordinal": None,
                "conditions": None,
                "determinism": edge.get("determinism"),
            }
        )
        name = f"{labels.get(edge['source'], edge['source'])} → {labels.get(edge['target'], edge['target'])}"
        claims.append(
            claim(
                "EDGE",
                key,
                name,
                RELATIONS.get(relation, relation),
                edge["statement"],
                cite(edge.get("provenance", [])),
                draft_reason,
                {"edge": key.split(":", 2)[2]},
            )
        )
    for item in data.get("evidence", []):
        if item.get("misleading"):
            continue
        related = [f"inf:{domain}:{k}" for k in item.get("relevant_nodes", [])]
        subject = related[0] if related else f"inf:{domain}"
        rows = [
            {
                "sourceId": by_citation[item.get("citation", "")],
                "locator": None,
                "quote": None,
                "quoteClipped": False,
                "quoteCheck": "NA",
                "relation": EVIDENCE_RELATION.get(item.get("evidence_relation", ""), "CONTEXTUAL"),
                "note": None,
            }
        ]
        claims.append(
            claim(
                "CONCEPT",
                subject,
                labels.get(subject.rsplit(":", 1)[-1], subject),
                "SUPPORTING_EVIDENCE",
                item["text"],
                rows,
                f"draft seed evidence ({item.get('evidence_relation')}), paraphrased",
                {"evidence": item["key"]},
                related,
            )
        )
    return {
        "domain": {"file": domain, "subCategorySlug": sub_slug, **data.get("domain", {})},
        "sources": list(sources.values()),
        "concepts": concepts,
        "edges": edges,
        "claims": claims,
        "chains": [
            {**chain, "nodes": [f"inf:{domain}:{n}" for n in chain.get("nodes", [])]}
            for chain in data.get("chains", [])
        ],
    }


def file_sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def build(immersive_root: Path = IMMERSIVE_ROOT, inferential_root: Path = INFERENTIAL_ROOT) -> dict[str, Any]:
    master = {c.slug: c for c in parse_master(read_json(MASTER_FILE))}
    traditions: list[dict[str, Any]] = []
    domains: list[dict[str, Any]] = []
    sources: dict[str, dict[str, Any]] = {}
    concepts: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    inputs: dict[str, str] = {}

    def absorb(part: dict[str, Any]) -> None:
        for src in part["sources"]:
            sources.setdefault(src["id"], src)
        concepts.extend(part["concepts"])
        edges.extend(part["edges"])
        claims.extend(part["claims"])

    for file_slug, craft_slug in IMMERSIVE_TO_MASTER.items():
        path = immersive_root / "traditions" / file_slug / "tradition.json"
        if not path.exists():
            raise FileNotFoundError(path)
        craft = master[craft_slug]
        part = convert_immersive(read_json(path), file_slug, craft_slug, craft.sub_category_slug)
        traditions.append(part["tradition"])
        absorb(part)
        inputs[f"immersive-episteme/content/traditions/{file_slug}/tradition.json"] = file_sha1(path)
    shared = immersive_root / "shared" / "craft-science.json"
    part = convert_immersive(read_json(shared), "shared", None, SHARED_SCIENCE_SUB_CATEGORY)
    traditions.append(part["tradition"])
    absorb(part)
    inputs["immersive-episteme/content/shared/craft-science.json"] = file_sha1(shared)
    for domain, sub_slug in INFERENTIAL_TO_SUB_CATEGORY.items():
        path = inferential_root / f"{domain}.json"
        if not path.exists():
            raise FileNotFoundError(path)
        part = convert_inferential(read_json(path), domain, sub_slug)
        domains.append({**part["domain"], "chains": part["chains"]})
        absorb(part)
        inputs[f"inferential-system/data/seed/{domain}.json"] = file_sha1(path)

    seen: set[str] = set()
    unique_claims: list[dict[str, Any]] = []
    for row in claims:
        if row["id"] not in seen:
            seen.add(row["id"])
            unique_claims.append(row)
    summary: dict[str, Any] = {
        "claims": len(unique_claims),
        "concepts": len(concepts),
        "edges": len(edges),
        "sources": len(sources),
        "byLevel": {},
        "byCraft": {},
        "bySubCategory": {},
    }
    for row in unique_claims:
        summary["byLevel"][row["evidenceLevel"]] = summary["byLevel"].get(row["evidenceLevel"], 0) + 1
        craft_key = row["craftSlug"] or "(sub-category)"
        summary["byCraft"][craft_key] = summary["byCraft"].get(craft_key, 0) + 1
        summary["bySubCategory"][row["subCategorySlug"]] = summary["bySubCategory"].get(row["subCategorySlug"], 0) + 1
    return {
        "version": 1,
        "about": "Seed knowledge converted from immersive-episteme (six traditions plus shared craft science) "
        "and inferential-system (block printing, terracotta, wood carving draft graphs). Claims carry their "
        "quoted passages and sources. 'PROVISIONAL' means a verbatim quote was re-found by the upstream source "
        "check; 'HYPOTHESIS' means no checked quote (inferential drafts, or a source that states it as a "
        "hypothesis). Imports are written by the system actor 'import' and are never above PROVISIONAL.",
        "inputs": inputs,
        "summary": summary,
        "traditions": traditions,
        "domains": domains,
        "sources": sorted(sources.values(), key=lambda s: s["id"]),
        "concepts": concepts,
        "edges": edges,
        "claims": unique_claims,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert the science seeds into seed_claims.json.")
    parser.add_argument("--immersive-root", default=str(IMMERSIVE_ROOT))
    parser.add_argument("--inferential-root", default=str(INFERENTIAL_ROOT))
    parser.add_argument("--output", default=str(SEED_CLAIMS_FILE))
    args = parser.parse_args(argv)
    result = build(Path(args.immersive_root), Path(args.inferential_root))
    write_json(Path(args.output), result)
    print(f"wrote {args.output}: {result['summary']['claims']} claims, levels {result['summary']['byLevel']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
