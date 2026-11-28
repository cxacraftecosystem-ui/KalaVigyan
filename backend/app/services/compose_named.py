from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure
from app.models import Claim, Concept
from app.research.blocks import named_in_texts
from app.research.component_specs_general_delivery import UNIT_TEXT_MAX
from app.research.vocabulary import FACT_LEVELS
from app.retrieval.citation_access import CONCEPT_SUBJECT
from app.sources.reference.pubchem import PubChemCompound

from .compose_held import CraftHeld, HeldCompound, HeldFact, NamedCompound
from .knowledge_api import every_fact, known_craft

__all__ = [
    "NO_RECORD",
    "RECORD_UNREAD",
    "UNNAMED",
    "CompoundRecords",
    "Naming",
    "fact_named_compound",
    "facts_naming",
    "held_by_material",
    "page_facts",
]

NO_RECORD = (
    "the compound CID {cid}: PubChem holds no compound under that CID; lookup with the compound's name "
    "gives its CID"
)
RECORD_UNREAD = "PubChem's record of CID {cid}, which could not be read just now; compose it again later"
UNNAMED = (
    "a fact of {craft} that names {name} (PubChem CID {cid}): none of its facts names it by PubChem's name or "
    "a synonym, and none of its materials is held as it; propose_facts states what the page says of {name}, "
    "then compose it again"
)
WORD_LIKE = re.compile(r"^[A-Za-z][A-Za-z' -]{2,}[A-Za-z]$")


class CompoundRecords(Protocol):
    async def compound(self, cid: int) -> PubChemCompound | None: ...

    async def synonyms(self, cid: int) -> list[str]: ...


@dataclass(frozen=True)
class Naming:
    craft: CraftHeld
    compounds: tuple[NamedCompound, ...] = ()
    problem: str | None = None


def held_by_material(craft: CraftHeld, cid: int) -> bool:
    return any(
        material.compound is not None and material.compound.cid == cid and craft.stated(material.claim_ids)
        for material in craft.materials
    )


def facts_naming(names: Iterable[str], facts: Mapping[uuid.UUID, HeldFact]) -> tuple[uuid.UUID, ...]:
    found: dict[uuid.UUID, None] = {}
    for name in dict.fromkeys(name.strip() for name in names):
        if name:
            found |= {claim: None for claim, fact in facts.items() if named_in_texts(name, [fact.text])}
    return tuple(found)


async def page_facts(session: AsyncSession, slug: str) -> dict[uuid.UUID, HeldFact]:
    craft = await known_craft(session, slug)
    facts, _ = await every_fact(session, craft)
    shown = {
        fact.id: fact.text for fact in facts if fact.level in FACT_LEVELS and len(fact.text) <= UNIT_TEXT_MAX
    }
    if not shown:
        return {}
    owned = select(Claim.id).join(
        Concept, and_(Claim.subjectType == CONCEPT_SUBJECT, Claim.subjectId == Concept.id)
    )
    own = set(await session.scalars(owned.where(Claim.id.in_(list(shown)), Concept.craftId == craft.id)))
    return {claim: HeldFact(claim, text) for claim, text in shown.items() if claim in own}


async def fact_named_compound(
    craft: CraftHeld, cid: int, records: CompoundRecords, facts: Mapping[uuid.UUID, HeldFact]
) -> Naming:
    try:
        record = await records.compound(cid)
        if record is None:
            return Naming(craft, problem=NO_RECORD.format(cid=cid))
        claims = facts_naming([record.title], facts) or facts_naming(
            _word_like(await records.synonyms(cid)), facts
        )
    except ExternalFailure:
        return Naming(craft, problem=RECORD_UNREAD.format(cid=cid))
    if not claims:
        return Naming(craft, problem=UNNAMED.format(craft=craft.name, name=record.title, cid=cid))
    compound = NamedCompound(HeldCompound(cid, record.title, record.formula), claims)
    named = replace(craft, facts={**craft.facts, **{claim: facts[claim] for claim in claims}})
    return Naming(named, (compound,))


def _word_like(names: Sequence[str]) -> list[str]:
    return [name for name in names if WORD_LIKE.match(name)]
