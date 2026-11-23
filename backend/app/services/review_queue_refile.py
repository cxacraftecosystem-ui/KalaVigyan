from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import Claim, Concept
from app.research.page_revalidation import PageOwners
from app.research.review_queue import FACTS, QueueApproval
from app.research.write_back import WriteBackSubject

from .candidate_store import category_subject
from .claim_writer import SHARED_CONCEPT_KEYS, concept_id_for, craft_keys
from .curation_keys import DISCIPLINE_CONCEPT_TYPES
from .page_revalidation import claim_owners
from .write_back_crafts import MATERIAL_SCIENCE_FIELDS

__all__ = [
    "FAMILY_FIELDS_ONLY",
    "REFILED_FAMILY_NOTE",
    "REFILED_NOTE",
    "filed_owners",
    "refile_fact",
    "refile_family",
    "refiling_problem",
]

CONCEPT_SUBJECT = "CONCEPT"
REFILED_NOTE = "filed under {craft}"
REFILED_FAMILY_NOTE = "filed under the family science of {family}"
ONLY_FACTS = "Only a fact is filed under another craft or a family's science."
ONLY_CONCEPTS = "Only a fact about a concept can be filed under another craft or a family's science."
FAMILY_FIELDS_ONLY = "Only a chemistry, physics or materials fact is filed under its family's science."


def refiling_problem(kind: str, approval: QueueApproval) -> str | None:
    return ONLY_FACTS if approval.filed_under is not None and kind != FACTS else None


async def filed_owners(
    session: AsyncSession, kind: str, item_id: uuid.UUID, filed_under: str | None
) -> PageOwners:
    if filed_under is None or kind != FACTS:
        return PageOwners()
    return await claim_owners(session, [item_id])


async def refile_fact(session: AsyncSession, claim: Claim, craft_slug: str) -> None:
    concept = await _concept_of(session, claim)
    keys = await craft_keys(session, craft_slug)
    subject = WriteBackSubject(concept_type=concept.type, concept_name=concept.name)
    claim.subjectId = await concept_id_for(session, keys, subject)


async def refile_family(session: AsyncSession, claim: Claim, category_slug: str) -> None:
    await _concept_of(session, claim)
    field = claim.field
    if field is None or field not in MATERIAL_SCIENCE_FIELDS:
        raise InvalidInput(FAMILY_FIELDS_ONLY)
    family = await category_subject(session, category_slug)
    if family.name is None:
        raise InvalidInput(f"No category has the slug {category_slug!r}")
    subject = WriteBackSubject(concept_type=DISCIPLINE_CONCEPT_TYPES[field], concept_name=family.name)
    claim.subjectId = await concept_id_for(session, SHARED_CONCEPT_KEYS, subject)


async def _concept_of(session: AsyncSession, claim: Claim) -> Concept:
    concept = await session.get(Concept, claim.subjectId) if claim.subjectType == CONCEPT_SUBJECT else None
    if concept is None:
        raise InvalidInput(ONLY_CONCEPTS)
    return concept
