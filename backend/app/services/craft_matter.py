from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Compound, Source, Term, TermConcept
from app.research.blocks import ExplainerSentence, named_in
from app.research.crafts import CraftRef
from app.research.explainer import Block
from app.research.retrieval import EVERY_CHUNK_ACLS
from app.science.records import CompoundRecord, MaterialRecord, ProcessRecords

from .craft_process import process_records
from .knowledge_view import resolve_craft, source_ref

__all__ = [
    "CraftMatter",
    "GlossaryTerm",
    "MaterialRows",
    "MatterReads",
    "craft_matter",
    "first_naming",
    "material_rows",
    "section_sentences",
]


@dataclass(frozen=True)
class GlossaryTerm:
    key: str
    label: str
    aliases: tuple[str, ...]
    local_names: tuple[str, ...]
    wikidata_id: str | None

    def surfaces(self) -> tuple[str, ...]:
        return (self.label, *self.aliases, *self.local_names)


@dataclass(frozen=True)
class MaterialRows:
    material_id: uuid.UUID
    uses: tuple[MaterialRecord, ...]
    terms: tuple[GlossaryTerm, ...]

    @property
    def name(self) -> str:
        return self.uses[0].name

    @property
    def kind(self) -> str:
        return self.uses[0].kind

    @property
    def compound(self) -> CompoundRecord | None:
        return self.uses[0].compound

    def surfaces(self) -> tuple[str, ...]:
        names = dict.fromkeys(use.name for use in self.uses)
        return (*names, *(surface for term in self.terms for surface in term.surfaces()))


@dataclass(frozen=True)
class CraftMatter:
    records: ProcessRecords
    materials: tuple[MaterialRows, ...] = ()
    compounds: Mapping[uuid.UUID, CompoundRecord] = field(default_factory=dict)
    record_sources: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


async def craft_matter(sessions: async_sessionmaker[AsyncSession], craft: CraftRef) -> CraftMatter | None:
    async with sessions() as session:
        found = await resolve_craft(session, craft.slug)
        if found is None:
            return None
        records = await process_records(session, found, acls=EVERY_CHUNK_ACLS)
        terms = await _concept_terms(session, [m.concept_id for m in records.materials if m.concept_id])
        compounds = await _compounds(session, records)
        sources = await _record_sources(session, [c.source_id for c in compounds.values() if c.source_id])
    return CraftMatter(
        records=records,
        materials=material_rows(records.materials, terms),
        compounds=compounds,
        record_sources=sources,
    )


class MatterReads:
    def __init__(self) -> None:
        self._read: dict[str, CraftMatter | None] = {}
        self._lock = asyncio.Lock()

    async def read(self, sessions: async_sessionmaker[AsyncSession], craft: CraftRef) -> CraftMatter | None:
        async with self._lock:
            if craft.slug not in self._read:
                self._read[craft.slug] = await craft_matter(sessions, craft)
            return self._read[craft.slug]


def section_sentences(blocks: Iterable[Block]) -> list[ExplainerSentence]:
    return [
        sentence
        for block in blocks
        for sentence in block.cited_sentences()
        if isinstance(sentence, ExplainerSentence)
    ]


def first_naming(
    sentences: Sequence[ExplainerSentence], surfaces: Iterable[str], term_keys: Iterable[str] = ()
) -> int | None:
    names = [surface for surface in dict.fromkeys(surfaces) if surface.strip()]
    keys = set(term_keys)
    for position, sentence in enumerate(sentences):
        marked = {span.term_key for span in sentence.terms}
        if marked & keys or any(named_in(name, sentence) for name in names):
            return position
    return None


def material_rows(
    uses: Iterable[MaterialRecord], terms: Mapping[uuid.UUID, tuple[GlossaryTerm, ...]]
) -> tuple[MaterialRows, ...]:
    grouped: dict[uuid.UUID, list[MaterialRecord]] = {}
    for use in uses:
        if use.material_id is not None:
            grouped.setdefault(use.material_id, []).append(use)
    return tuple(
        MaterialRows(
            material_id, tuple(found), terms.get(found[0].concept_id, ()) if found[0].concept_id else ()
        )
        for material_id, found in grouped.items()
    )


async def _concept_terms(
    session: AsyncSession, concept_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[GlossaryTerm, ...]]:
    if not concept_ids:
        return {}
    rows = await session.execute(
        select(TermConcept.conceptId, Term)
        .join(Term, Term.id == TermConcept.termId)
        .where(TermConcept.conceptId.in_(list(dict.fromkeys(concept_ids))))
        .order_by(Term.key)
    )
    found: dict[uuid.UUID, list[GlossaryTerm]] = {}
    for concept_id, term in rows.tuples():
        found.setdefault(concept_id, []).append(
            GlossaryTerm(
                key=term.key,
                label=term.label,
                aliases=tuple(term.aliases),
                local_names=tuple(term.localNames),
                wikidata_id=term.wikidataId,
            )
        )
    return {concept_id: tuple(terms) for concept_id, terms in found.items()}


async def _compounds(session: AsyncSession, records: ProcessRecords) -> dict[uuid.UUID, CompoundRecord]:
    wanted = [m.compound.id for m in records.materials if m.compound is not None]
    wanted += [s.compound_id for r in records.reactions for s in r.species if s.compound_id is not None]
    if not wanted:
        return {}
    rows = await session.scalars(select(Compound).where(Compound.id.in_(list(dict.fromkeys(wanted)))))
    return {
        row.id: CompoundRecord(row.id, row.name, row.formula, row.pubchemCid, row.sourceId) for row in rows
    }


async def _record_sources(
    session: AsyncSession, source_ids: Sequence[uuid.UUID]
) -> dict[str, Mapping[str, Any]]:
    if not source_ids:
        return {}
    rows = await session.scalars(select(Source).where(Source.id.in_(list(dict.fromkeys(source_ids)))))
    return {str(row.id): source_ref(row) for row in rows}
