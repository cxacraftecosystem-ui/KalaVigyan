from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from source_authors import split_authors

from seed_terms import HYPOTHESIS, PROVISIONAL, RELATIONS, ClaimSubject, SeedClaim, concept_type, stage_type

__all__ = [
    "QUOTE_MAX",
    "clip_quote",
    "convert_immersive",
    "evidence_rows",
    "immersive_source",
    "level_for",
    "publication_kind",
    "stage_ordinals",
]

QUOTE_MAX = 300

RELIABILITY = {"high": "A", "medium": "B", "low": "C"}


@dataclass(frozen=True)
class _Tradition:
    file_slug: str
    craft_slug: str | None
    sub_slug: str
    ordinals: dict[str, int]
    titles: dict[str, str]


def clip_quote(quote: str) -> tuple[str, bool]:
    quote = " ".join(str(quote or "").split())
    if len(quote) <= QUOTE_MAX:
        return quote, False
    cut = quote[:QUOTE_MAX]
    space = cut.rfind(" ")
    return (cut[:space] if space > QUOTE_MAX // 2 else cut).rstrip(" ,;:"), True


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
    concepts = data.get("concepts", [])
    relationships = data.get("relationships", [])
    titles = {c["key"]: c["title"] for c in concepts}
    tradition = _Tradition(file_slug, craft_slug, sub_slug, stage_ordinals(data), titles)
    edge_claims = (_edge_claim(rel, tradition) for rel in relationships)
    claims = [claim for concept in concepts for claim in _concept_claims(concept, tradition)]
    claims += [claim for claim in edge_claims if claim is not None]
    return {
        "tradition": _tradition_row(data, tradition),
        "sources": [immersive_source(file_slug, s) for s in data.get("sources", [])],
        "concepts": [_concept_row(concept, tradition) for concept in concepts],
        "edges": [_edge_row(rel) for rel in relationships],
        "claims": claims,
    }


def _tradition_row(data: dict[str, Any], tradition: _Tradition) -> dict[str, Any]:
    gi = data.get("gi") or None
    return {
        "file": tradition.file_slug,
        "craftSlug": tradition.craft_slug,
        "subCategorySlug": tradition.sub_slug,
        "name": data.get("name"),
        "altNames": data.get("alt_names", []),
        "summary": data.get("summary"),
        "region": data.get("region") or None,
        "gi": {**gi, "sourceIds": [f"ie:{tradition.file_slug}:{s}" for s in gi.get("source_ids", [])]} if gi else None,
    }


def _concept_stage(concept: dict[str, Any], tradition: _Tradition) -> dict[str, Any] | None:
    if concept["type"] != "process_stage":
        return None
    return {
        "key": f"ie:{concept['key']}",
        "title": concept["title"],
        "ordinal": tradition.ordinals.get(concept["key"]),
        "stageType": stage_type(concept["title"], concept.get("summary", "")),
    }


def _concept_row(concept: dict[str, Any], tradition: _Tradition) -> dict[str, Any]:
    return {
        "key": f"ie:{concept['key']}",
        "craftSlug": tradition.craft_slug,
        "subCategorySlug": tradition.sub_slug,
        "type": concept_type(concept["type"]),
        "category": concept.get("category"),
        "name": concept["title"],
        "description": concept.get("summary"),
        "localTerms": concept.get("local_terms", []),
        "provenanceKind": concept.get("provenance_kind"),
        "stage": _concept_stage(concept, tradition),
        "compares": [f"ie:{k}" for k in concept.get("compares", [])],
    }


def _concept_claims(concept: dict[str, Any], tradition: _Tradition) -> list[dict[str, Any]]:
    subject = ClaimSubject("CONCEPT", f"ie:{concept['key']}", concept["title"], concept_type(concept["type"]))
    checked = concept.get("verification_state") == "verified"
    claims: list[dict[str, Any]] = []
    for index, claim in enumerate(concept.get("claims", [])):
        rows = evidence_rows(tradition.file_slug, claim.get("evidence", []), checked)
        level, reason = level_for(concept.get("provenance_kind"), rows)
        seeded = SeedClaim(
            craft_slug=tradition.craft_slug,
            sub_slug=tradition.sub_slug,
            subject=subject,
            text=claim["text"],
            stage=_concept_stage(concept, tradition),
            level=level,
            reason=reason,
            provenance_kind=concept.get("provenance_kind"),
            sources=rows,
            import_ref={
                "repo": "immersive-episteme",
                "file": tradition.file_slug,
                "key": concept["key"],
                "claim": index,
            },
        )
        claims.append(seeded.row())
    return claims


def _edge_key(rel: dict[str, Any]) -> str:
    return f"ie:{rel['source']}|{rel['type']}|{rel['target']}"


def _edge_row(rel: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": _edge_key(rel),
        "src": f"ie:{rel['source']}",
        "dst": f"ie:{rel['target']}",
        "relation": RELATIONS.get(rel["type"], rel["type"]),
        "sourceRelation": rel["type"],
        "ordinal": rel.get("ordinal"),
        "conditions": rel.get("conditions"),
    }


def _edge_stage(rel: dict[str, Any], tradition: _Tradition) -> dict[str, Any] | None:
    source = rel["source"]
    if not (tradition.titles.get(source) and tradition.ordinals.get(source)):
        return None
    return {"key": f"ie:{source}", "title": tradition.titles[source], "ordinal": tradition.ordinals[source]}


def _edge_claim(rel: dict[str, Any], tradition: _Tradition) -> dict[str, Any] | None:
    if rel["type"] == "BELONGS_TO" or not rel.get("explanation"):
        return None
    edge_key = _edge_key(rel)
    titles = tradition.titles
    name = f"{titles.get(rel['source'], rel['source'])} → {titles.get(rel['target'], rel['target'])}"
    rows = evidence_rows(tradition.file_slug, rel.get("evidence", []), rel.get("verification_state") == "verified")
    level, reason = level_for(rel.get("provenance_kind"), rows)
    return SeedClaim(
        craft_slug=tradition.craft_slug,
        sub_slug=tradition.sub_slug,
        subject=ClaimSubject("EDGE", edge_key, name, RELATIONS.get(rel["type"], rel["type"])),
        text=rel["explanation"],
        stage=_edge_stage(rel, tradition),
        level=level,
        reason=reason,
        provenance_kind=rel.get("provenance_kind"),
        sources=rows,
        import_ref={"repo": "immersive-episteme", "file": tradition.file_slug, "relationship": edge_key[3:]},
    ).row()
