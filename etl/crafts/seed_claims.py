from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common import read_json, write_json

from app.data.craft_master_loader import MASTER_FILE, SEED_CLAIMS_FILE, MasterCraft, parse_master

from seed_immersive import convert_immersive
from seed_inferential import convert_inferential
from traditions import (
    IMMERSIVE_ROOT,
    IMMERSIVE_TO_MASTER,
    INFERENTIAL_ROOT,
    INFERENTIAL_TO_SUB_CATEGORY,
    SHARED_SCIENCE_SUB_CATEGORY,
)

__all__ = ["build", "file_sha1", "main"]

ABOUT = (
    "Seed knowledge converted from immersive-episteme (six traditions plus shared craft science) "
    "and inferential-system (block printing, terracotta, wood carving draft graphs). Claims carry their "
    "quoted passages and sources. 'PROVISIONAL' means a verbatim quote was re-found by the upstream source "
    "check; 'HYPOTHESIS' means no checked quote (inferential drafts, or a source that states it as a "
    "hypothesis). Imports are written by the system actor 'import' and are never above PROVISIONAL."
)


@dataclass
class _Converted:
    traditions: list[dict[str, Any]] = field(default_factory=list)
    domains: list[dict[str, Any]] = field(default_factory=list)
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    concepts: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    inputs: dict[str, str] = field(default_factory=dict)

    def absorb(self, part: dict[str, Any], input_name: str, path: Path) -> None:
        for src in part["sources"]:
            self.sources.setdefault(src["id"], src)
        self.concepts.extend(part["concepts"])
        self.edges.extend(part["edges"])
        self.claims.extend(part["claims"])
        self.inputs[input_name] = file_sha1(path)


def file_sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def build(immersive_root: Path = IMMERSIVE_ROOT, inferential_root: Path = INFERENTIAL_ROOT) -> dict[str, Any]:
    master = {c.slug: c for c in parse_master(read_json(MASTER_FILE))}
    converted = _Converted()
    _convert_traditions(converted, immersive_root, master)
    _convert_domains(converted, inferential_root)
    claims = _unique_claims(converted.claims)
    return {
        "version": 1,
        "about": ABOUT,
        "inputs": converted.inputs,
        "summary": _summary(claims, converted),
        "traditions": converted.traditions,
        "domains": converted.domains,
        "sources": sorted(converted.sources.values(), key=lambda s: s["id"]),
        "concepts": converted.concepts,
        "edges": converted.edges,
        "claims": claims,
    }


def _convert_traditions(converted: _Converted, immersive_root: Path, master: dict[str, MasterCraft]) -> None:
    for file_slug, craft_slug in IMMERSIVE_TO_MASTER.items():
        path = immersive_root / "traditions" / file_slug / "tradition.json"
        if not path.exists():
            raise FileNotFoundError(path)
        part = convert_immersive(read_json(path), file_slug, craft_slug, master[craft_slug].sub_category_slug)
        converted.traditions.append(part["tradition"])
        converted.absorb(part, f"immersive-episteme/content/traditions/{file_slug}/tradition.json", path)
    shared = immersive_root / "shared" / "craft-science.json"
    part = convert_immersive(read_json(shared), "shared", None, SHARED_SCIENCE_SUB_CATEGORY)
    converted.traditions.append(part["tradition"])
    converted.absorb(part, "immersive-episteme/content/shared/craft-science.json", shared)


def _convert_domains(converted: _Converted, inferential_root: Path) -> None:
    for domain, sub_slug in INFERENTIAL_TO_SUB_CATEGORY.items():
        path = inferential_root / f"{domain}.json"
        if not path.exists():
            raise FileNotFoundError(path)
        part = convert_inferential(read_json(path), domain, sub_slug)
        converted.domains.append({**part["domain"], "chains": part["chains"]})
        converted.absorb(part, f"inferential-system/data/seed/{domain}.json", path)


def _unique_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in claims:
        if row["id"] not in seen:
            seen.add(row["id"])
            unique.append(row)
    return unique


def _summary(claims: list[dict[str, Any]], converted: _Converted) -> dict[str, Any]:
    return {
        "claims": len(claims),
        "concepts": len(converted.concepts),
        "edges": len(converted.edges),
        "sources": len(converted.sources),
        "byLevel": _tally(row["evidenceLevel"] for row in claims),
        "byCraft": _tally(row["craftSlug"] or "(sub-category)" for row in claims),
        "bySubCategory": _tally(row["subCategorySlug"] for row in claims),
    }


def _tally(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


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
