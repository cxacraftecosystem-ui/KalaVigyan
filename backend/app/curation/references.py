from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .dossier import Dossier
from .entities import Stage
from .fields import SUBJECT_KINDS
from .problems import Problem
from .records import Picture

__all__ = ["KINDS_BY_PART", "Reference", "id_problems", "reference_problems", "references"]

KINDS_BY_PART: Mapping[str, str] = MappingProxyType(
    {
        "sources": "source",
        "claims": "claim",
        "places": "place",
        "communities": "community",
        "stages": "stage",
        "materials": "material",
        "tools": "tool",
        "reactions": "reaction",
        "glossary": "term",
        "openQuestions": "question",
        "pictures": "picture",
    }
)


@dataclass(frozen=True)
class Reference:
    where: str
    kind: str
    ref: str
    as_fact: bool = True


def id_problems(dossier: Dossier) -> list[Problem]:
    found = []
    for part, ids in _ids_by_part(dossier).items():
        found += [
            Problem(part, f"{item} is used more than once") for item, n in Counter(ids).items() if n > 1
        ]
    return found


def reference_problems(dossier: Dossier) -> list[Problem]:
    known: dict[str, set[str]] = {kind: set() for kind in KINDS_BY_PART.values()}
    for part, ids in _ids_by_part(dossier).items():
        known[KINDS_BY_PART[part]].update(ids)
    return [
        Problem(reference.where, f"{reference.ref} names no {reference.kind} in the dossier")
        for reference in references(dossier)
        if reference.ref not in known[reference.kind]
    ]


def references(dossier: Dossier) -> Iterator[Reference]:
    yield from _claim_references(dossier)
    yield from _entity_references(dossier)
    yield from _record_references(dossier)
    yield from _note_references(dossier)
    yield from _overview_references(dossier)


def _ids_by_part(dossier: Dossier) -> dict[str, list[str]]:
    parts = {
        "sources": dossier.sources,
        "claims": dossier.claims,
        "places": dossier.places,
        "communities": dossier.communities,
        "stages": dossier.stages,
        "materials": dossier.materials,
        "tools": dossier.tools,
        "reactions": dossier.reactions,
        "glossary": dossier.glossary,
        "openQuestions": dossier.open_questions,
        "pictures": dossier.pictures,
    }
    return {part: [item.id for item in items] for part, items in parts.items()}


def _claims(where: str, claim_ids: Iterable[str], *, as_fact: bool = True) -> Iterator[Reference]:
    for claim_id in claim_ids:
        yield Reference(where, "claim", claim_id, as_fact)


def _claim_references(dossier: Dossier) -> Iterator[Reference]:
    for claim in dossier.claims:
        for quote in claim.quotes:
            yield Reference(claim.id, "source", quote.source_id)
        if claim.subject.ref is not None:
            yield Reference(claim.id, SUBJECT_KINDS[claim.subject.type], claim.subject.ref)


def _entity_references(dossier: Dossier) -> Iterator[Reference]:
    for item in (*dossier.places, *dossier.materials, *dossier.tools, *dossier.glossary):
        yield from _claims(item.id, item.claim_ids)
    for community in dossier.communities:
        yield from _claims(community.id, community.claim_ids)
        if community.place_id is not None:
            yield Reference(community.id, "place", community.place_id)
    for stage in dossier.stages:
        yield from _stage_references(stage)
    for reaction in dossier.reactions:
        yield from _claims(reaction.id, reaction.claim_ids)
        if reaction.stage_id is not None:
            yield Reference(reaction.id, "stage", reaction.stage_id)


def _stage_references(stage: Stage) -> Iterator[Reference]:
    timings = (stage.duration, stage.season)
    named = [
        stage.order_claim_id,
        stage.why_claim_id,
        stage.after.claim_id if stage.after is not None else None,
        *(timing.claim_id for timing in timings if timing is not None),
    ]
    yield from _claims(
        stage.id, [*stage.claim_ids, *(claim_id for claim_id in named if claim_id is not None)]
    )
    for material in stage.materials:
        yield Reference(stage.id, "material", material.material_id)
        yield Reference(stage.id, "claim", material.claim_id)
    for tool in stage.tools:
        yield Reference(stage.id, "tool", tool.tool_id)
        yield Reference(stage.id, "claim", tool.claim_id)


def _record_references(dossier: Dossier) -> Iterator[Reference]:
    for index, link in enumerate(dossier.environment):
        yield from _claims(f"environment.{index}", link.claim_ids)
        if link.place_id is not None:
            yield Reference(f"environment.{index}", "place", link.place_id)
    if dossier.market.gi is not None:
        yield from _claims("market.gi", dossier.market.gi.claim_ids)
    for index, price in enumerate(dossier.market.prices):
        yield Reference(f"market.prices.{index}", "claim", price.claim_id)
        yield Reference(f"market.prices.{index}", "place", price.place_id)
    for index, workforce in enumerate(dossier.market.workforce):
        yield Reference(f"market.workforce.{index}", "claim", workforce.claim_id)
    yield from _claims("market.imitation", dossier.market.imitation)
    for picture in dossier.pictures:
        yield from _claims(picture.id, picture.claim_ids)
        if picture.stage_id is not None:
            yield Reference(picture.id, "stage", picture.stage_id)
        yield from _placement_references(picture)
    for index, name in enumerate(dossier.native_names):
        yield Reference(f"nativeNames.{index}", "claim", name.claim_id)


def _placement_references(picture: Picture) -> Iterator[Reference]:
    placement = picture.placement
    if placement is None:
        return
    if placement.stage_id is not None:
        yield Reference(f"{picture.id}.placement", "stage", placement.stage_id)
    if placement.material_id is not None:
        yield Reference(f"{picture.id}.placement", "material", placement.material_id)


def _note_references(dossier: Dossier) -> Iterator[Reference]:
    for index, conflict in enumerate(dossier.conflicts):
        yield from _claims(f"conflicts.{index}", conflict.claim_ids, as_fact=False)
    for question in dossier.open_questions:
        yield from _claims(question.id, question.claim_ids, as_fact=False)


def _overview_references(dossier: Dossier) -> Iterator[Reference]:
    for where, sentence in dossier.overview.located_sentences():
        yield from _claims(where, sentence.claim_ids)
    for index, fact in enumerate(dossier.overview.key_facts):
        yield from _claims(f"overview.keyFacts.{index}", fact.claim_ids)
