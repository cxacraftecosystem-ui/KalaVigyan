from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import Claim, Concept
from app.research.page_revalidation import PageOwners
from app.research.review_queue import FACTS
from app.research.write_back import WriteBackSubject

from .claim_writer import concept_id_for, craft_keys
from .page_revalidation import claim_owners

__all__ = ["REFILED_NOTE", "filed_owners", "refile_fact", "refiling_problem"]

CONCEPT_SUBJECT = "CONCEPT"
REFILED_NOTE = "filed under {craft}"
ONLY_FACTS = "Only a fact is filed under another craft."
ONLY_CONCEPTS = "Only a fact about a concept can be filed under another craft."


def refiling_problem(kind: str, craft: str | None) -> str | None:
    return ONLY_FACTS if craft is not None and kind != FACTS else None


async def filed_owners(session: AsyncSession, kind: str, item_id: uuid.UUID, craft: str | None) -> PageOwners:
    if craft is None or kind != FACTS:
        return PageOwners()
    return await claim_owners(session, [item_id])


async def refile_fact(session: AsyncSession, claim: Claim, craft_slug: str) -> None:
    concept = await session.get(Concept, claim.subjectId) if claim.subjectType == CONCEPT_SUBJECT else None
    if concept is None:
        raise InvalidInput(ONLY_CONCEPTS)
    keys = await craft_keys(session, craft_slug)
    subject = WriteBackSubject(concept_type=concept.type, concept_name=concept.name)
    claim.subjectId = await concept_id_for(session, keys, subject)
