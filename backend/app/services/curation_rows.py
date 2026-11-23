from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.curation.check_file import CheckFile
from app.curation.dossier import Dossier
from app.curation.entities import Place
from app.curation.parts import Claim as DossierClaim, Source as DossierSource
from app.research.quotes import quote_key

from .curation_keys import (
    CURATED_PREDICATE,
    CURATED_STATUS,
    CURATION_ACTOR,
    DISCIPLINE_CONCEPT_TYPES,
    ENTITY_CONCEPT_TYPES,
    HYPOTHESIS_LEVEL,
    QUOTED_LEVEL,
    craft_concept_key,
    curated_id,
    day_start,
)

__all__ = [
    "CURATED_STORAGE",
    "ConceptPlan",
    "CraftTarget",
    "claim_level",
    "claim_rows",
    "claim_source_id",
    "claim_source_rows",
    "concept_plan",
    "curated_claim_rows",
    "differing_on",
    "place_concept_keys",
    "source_rows",
]

CURATED_STORAGE = "EXCERPT"
QUOTE_CHECK = "PASS"
DIRECT = "DIRECT"
HYPOTHESIS_REASON = "the source states it as uncertain, a theory or a legend"


@dataclass(frozen=True)
class CraftTarget:
    id: uuid.UUID
    slug: str
    name: str


@dataclass(frozen=True)
class ConceptPlan:
    rows: tuple[dict[str, Any], ...]
    ids: Mapping[str, uuid.UUID]
    craft_concepts: Mapping[str, uuid.UUID]
    places: Mapping[str, uuid.UUID]

    def subject(self, claim: DossierClaim) -> uuid.UUID:
        if claim.subject.type == "CRAFT":
            return self.ids[craft_concept_key(claim.discipline)]
        if claim.subject.type == "PLACE":
            return self.places[str(claim.subject.ref)]
        return self.ids[str(claim.subject.ref)]


def source_rows(dossier: Dossier, check: CheckFile) -> list[dict[str, Any]]:
    digests = {entry.source_id: entry.text_sha256 for entry in check.sources}
    return [_source_row(dossier.slug, source, digests.get(source.id)) for source in dossier.sources]


def _source_row(slug: str, source: DossierSource, digest: str | None) -> dict[str, Any]:
    external: dict[str, Any] = {
        "systemActor": CURATION_ACTOR,
        "curation": f"{slug}:{source.id}",
        "language": source.language,
        "access": source.access,
    }
    if source.archived_url:
        external["archivedUrl"] = source.archived_url
    return {
        "id": curated_id(slug, source.id),
        "kind": source.kind,
        "title": source.title,
        "authors": list(source.authors),
        "year": source.year,
        "doi": source.doi,
        "url": source.url,
        "publisher": source.publisher,
        "licence": source.licence,
        "reliability": source.reliability,
        "storage": CURATED_STORAGE,
        "sha256": digest,
        "retrievedAt": day_start(source.retrieved_at),
        "origin": "IMPORT",
        "sensitivity": "OPEN",
        "evidenceKind": source.sub_kind,
        "externalIds": external,
    }


def place_concept_keys(dossier: Dossier) -> dict[str, str]:
    first: dict[tuple[Any, ...], str] = {}
    keys: dict[str, str] = {}
    for place in dossier.places:
        group = first.setdefault(_place_identity(place), place.id)
        keys[place.id] = f"place:{group}"
    return keys


def _place_identity(place: Place) -> tuple[Any, ...]:
    return place.name.casefold(), place.kind, place.district, place.state, place.country


def concept_plan(dossier: Dossier, *, craft_id: uuid.UUID | None, name: str) -> ConceptPlan:
    named: dict[str, tuple[str, str, str | None]] = {}
    for discipline in dict.fromkeys(c.discipline for c in dossier.claims if c.subject.type == "CRAFT"):
        named[craft_concept_key(discipline)] = (DISCIPLINE_CONCEPT_TYPES[discipline], name, None)
    entity = ENTITY_CONCEPT_TYPES
    named.update((stage.id, (entity["STAGE"], stage.name, None)) for stage in dossier.stages)
    named.update((item.id, (entity["MATERIAL"], item.name, None)) for item in dossier.materials)
    named.update((item.id, (entity["TOOL"], item.name, None)) for item in dossier.tools)
    named.update((group.id, (entity["COMMUNITY"], group.name, None)) for group in dossier.communities)
    places = place_concept_keys(dossier)
    for place in dossier.places:
        named.setdefault(places[place.id], (entity["PLACE"], place.name, None))
    for term in dossier.glossary:
        named[term.id] = (entity["TERM"], term.term, term.meaning)
    ids = {key: curated_id(dossier.slug, "concept", key) for key in named}
    rows = tuple(
        {
            "id": ids[key],
            "craftId": craft_id,
            "subCategoryId": None,
            "type": concept_type,
            "name": concept_name,
            "description": description,
            "originRef": f"curation:{dossier.slug}:{key}",
            "sensitivity": "OPEN",
        }
        for key, (concept_type, concept_name, description) in named.items()
    )
    crafted = {key.split(":", 1)[1]: ids[key] for key in named if key.startswith("craft:")}
    subjects = {place_id: ids[key] for place_id, key in places.items()}
    return ConceptPlan(rows=rows, ids=ids, craft_concepts=crafted, places=subjects)


def claim_level(claim: DossierClaim) -> str:
    return HYPOTHESIS_LEVEL if claim.hypothesis else QUOTED_LEVEL


def claim_rows(dossier: Dossier, check: CheckFile, concepts: ConceptPlan) -> list[dict[str, Any]]:
    differ = differing_on(dossier)
    verified = f"every quote re-found verbatim by {check.tool} on {check.checked_at.date().isoformat()}"
    return [
        {
            "id": curated_id(dossier.slug, claim.id),
            "subjectType": "CONCEPT",
            "subjectId": concepts.subject(claim),
            "predicate": CURATED_PREDICATE,
            "text": claim.text,
            "textLang": "en",
            "evidenceLevel": claim_level(claim),
            "levelReason": HYPOTHESIS_REASON if claim.hypothesis else verified,
            "origin": "IMPORT",
            "status": CURATED_STATUS,
            "version": dossier.version,
            "createdByKind": "SYSTEM",
            "sensitivity": claim.sensitivity,
            "sourcesDiffer": claim.id in differ,
            "differsOn": differ.get(claim.id),
            "field": claim.discipline,
        }
        for claim in dossier.claims
    ]


def differing_on(dossier: Dossier) -> dict[str, str]:
    named: dict[str, str] = {}
    for conflict in dossier.conflicts:
        for claim_id in conflict.claim_ids:
            named.setdefault(claim_id, conflict.about)
    return named


def curated_claim_rows(dossier: Dossier, owner_column: str, owner_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        {
            "claimId": curated_id(dossier.slug, claim.id),
            owner_column: owner_id,
            "key": claim.id,
            "discipline": claim.discipline,
        }
        for claim in dossier.claims
    ]


def claim_source_id(slug: str, claim_key: str, source_key: str, quote: str) -> uuid.UUID:
    return curated_id(slug, "quote", claim_key, source_key, quote_key(quote))


def claim_source_rows(dossier: Dossier, check: CheckFile) -> list[dict[str, Any]]:
    slug = dossier.slug
    retrieved = {source.id: day_start(source.retrieved_at) for source in dossier.sources}
    rows: dict[uuid.UUID, dict[str, Any]] = {}
    for claim in dossier.claims:
        for quote in claim.quotes:
            row_id = claim_source_id(slug, claim.id, quote.source_id, quote.quote)
            rows.setdefault(
                row_id,
                {
                    "id": row_id,
                    "claimId": curated_id(slug, claim.id),
                    "sourceId": curated_id(slug, quote.source_id),
                    "locator": quote.locator,
                    "quote": quote.quote,
                    "quoteCheck": QUOTE_CHECK,
                    "checkedAt": check.checked_at,
                    "relation": DIRECT,
                    "foundBy": CURATION_ACTOR,
                    "retrievedAt": retrieved[quote.source_id],
                },
            )
    return list(rows.values())
