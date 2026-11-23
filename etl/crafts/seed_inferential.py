from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

from seed_terms import HYPOTHESIS, RELATIONS, ClaimSubject, SeedClaim, concept_type, sha1_text, stage_type

__all__ = ["citation_kind", "convert_inferential", "inferential_sources"]

EVIDENCE_RELATION = {
    "analogous": "ANALOGOUS",
    "general_principle": "GENERAL_PRINCIPLE",
    "contextual": "CONTEXTUAL",
    "derived": "CONTEXTUAL",
}

DRAFT_REASON = "draft seed: textbook citation without a checked quote"


@dataclass(frozen=True)
class _Domain:
    name: str
    sub_slug: str
    by_citation: dict[str, str]
    labels: dict[str, str]


def citation_kind(source_type: str, citation: str) -> str:
    if source_type == "scientific_literature":
        return "PAPER" if re.search(r"\bjournal\b|\d+\(\d+\)|doi", citation, re.I) else "BOOK"
    return "OTHER"


def inferential_sources(domain: str, data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    cited = [
        (prov.get("source_type", "other"), prov.get("citation", ""))
        for row in data.get("nodes", []) + data.get("edges", [])
        for prov in row.get("provenance", [])
    ]
    cited += [(item.get("source_type", "other"), item.get("citation", "")) for item in data.get("evidence", [])]
    for source_type, citation in cited:
        sid = "inf:" + sha1_text(citation)[:12]
        if sid not in out:
            out[sid] = _inferential_source(sid, domain, source_type, citation)
    return out


def _inferential_source(sid: str, domain: str, source_type: str, citation: str) -> dict[str, Any]:
    programme = source_type == "expert_interpretation"
    return {
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


def convert_inferential(data: dict[str, Any], domain: str, sub_slug: str) -> dict[str, Any]:
    sources = inferential_sources(domain, data)
    by_citation = {s["title"]: sid for sid, s in sources.items()}
    labels = {n["key"]: n["label"] for n in data.get("nodes", [])}
    scope = _Domain(domain, sub_slug, by_citation, labels)
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    evidence = [item for item in data.get("evidence", []) if not item.get("misleading")]
    return {
        "domain": {"file": domain, "subCategorySlug": sub_slug, **data.get("domain", {})},
        "sources": list(sources.values()),
        "concepts": [_node_concept(node, scope) for node in nodes],
        "edges": [_edge_row(edge, scope) for edge in edges],
        "claims": [
            *(_node_claim(node, scope) for node in nodes),
            *(_edge_claim(edge, scope) for edge in edges),
            *(_evidence_claim(item, scope) for item in evidence),
        ],
        "chains": [
            {**chain, "nodes": [f"inf:{domain}:{n}" for n in chain.get("nodes", [])]}
            for chain in data.get("chains", [])
        ],
    }


def _cited(provenance: list[dict[str, Any]], scope: _Domain) -> list[dict[str, Any]]:
    return [
        {
            "sourceId": scope.by_citation[p.get("citation", "")],
            "locator": p.get("detail"),
            "quote": None,
            "quoteClipped": False,
            "quoteCheck": "NA",
            "relation": "GENERAL_PRINCIPLE" if p.get("source_type") == "scientific_literature" else "CONTEXTUAL",
            "note": None,
        }
        for p in provenance
    ]


def _draft_claim(
    scope: _Domain, subject: ClaimSubject, text: str, rows: list[dict[str, Any]], ref: dict[str, Any]
) -> SeedClaim:
    return SeedClaim(
        craft_slug=None,
        sub_slug=scope.sub_slug,
        subject=subject,
        text=text,
        stage=None,
        level=HYPOTHESIS,
        reason=DRAFT_REASON,
        provenance_kind=None,
        sources=rows,
        import_ref={"repo": "inferential-system", "file": scope.name, **ref},
        related_keys=[],
    )


def _node_key(node: dict[str, Any], scope: _Domain) -> str:
    return f"inf:{scope.name}:{node['key']}"


def _node_concept(node: dict[str, Any], scope: _Domain) -> dict[str, Any]:
    key = _node_key(node, scope)
    stage = {"key": key, "title": node["label"], "ordinal": None, "stageType": stage_type(node["label"])}
    return {
        "key": key,
        "craftSlug": None,
        "subCategorySlug": scope.sub_slug,
        "type": concept_type(node["node_type"]),
        "category": node.get("knowledge_domain"),
        "name": node["label"],
        "description": node.get("statement"),
        "localTerms": node.get("aliases", []),
        "provenanceKind": None,
        "stage": stage if node["node_type"] == "process_stage" else None,
        "compares": [],
    }


def _node_claim(node: dict[str, Any], scope: _Domain) -> dict[str, Any]:
    subject = ClaimSubject("CONCEPT", _node_key(node, scope), node["label"], concept_type(node["node_type"]))
    rows = _cited(node.get("provenance", []), scope)
    return _draft_claim(scope, subject, node["statement"], rows, {"node": node["key"]}).row()


def _edge_key(edge: dict[str, Any], scope: _Domain) -> str:
    return f"inf:{scope.name}:{edge['source']}|{edge['relation'].upper()}|{edge['target']}"


def _edge_row(edge: dict[str, Any], scope: _Domain) -> dict[str, Any]:
    relation = edge["relation"].upper()
    return {
        "key": _edge_key(edge, scope),
        "src": f"inf:{scope.name}:{edge['source']}",
        "dst": f"inf:{scope.name}:{edge['target']}",
        "relation": RELATIONS.get(relation, relation),
        "sourceRelation": edge["relation"],
        "ordinal": None,
        "conditions": None,
        "determinism": edge.get("determinism"),
    }


def _edge_claim(edge: dict[str, Any], scope: _Domain) -> dict[str, Any]:
    relation = edge["relation"].upper()
    key = _edge_key(edge, scope)
    name = f"{scope.labels.get(edge['source'], edge['source'])} → {scope.labels.get(edge['target'], edge['target'])}"
    subject = ClaimSubject("EDGE", key, name, RELATIONS.get(relation, relation))
    rows = _cited(edge.get("provenance", []), scope)
    return _draft_claim(scope, subject, edge["statement"], rows, {"edge": key.split(":", 2)[2]}).row()


def _evidence_claim(item: dict[str, Any], scope: _Domain) -> dict[str, Any]:
    related = [f"inf:{scope.name}:{k}" for k in item.get("relevant_nodes", [])]
    key = related[0] if related else f"inf:{scope.name}"
    subject = ClaimSubject("CONCEPT", key, scope.labels.get(key.rsplit(":", 1)[-1], key), "SUPPORTING_EVIDENCE")
    rows = [
        {
            "sourceId": scope.by_citation[item.get("citation", "")],
            "locator": None,
            "quote": None,
            "quoteClipped": False,
            "quoteCheck": "NA",
            "relation": EVIDENCE_RELATION.get(item.get("evidence_relation", ""), "CONTEXTUAL"),
            "note": None,
        }
    ]
    drafted = _draft_claim(scope, subject, item["text"], rows, {"evidence": item["key"]})
    reason = f"draft seed evidence ({item.get('evidence_relation')}), paraphrased"
    return replace(drafted, reason=reason, related_keys=related).row()
