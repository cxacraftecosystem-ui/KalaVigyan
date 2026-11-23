from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Refused
from app.models import Claim, Concept, CraftGiRecord, StructureProposal, User
from app.research.structure_proposals import (
    CONFLICT,
    GI_RECORD,
    GLOSSARY_TERM,
    GiRecordItem,
    GroupNameItem,
    parsed_item,
)

from .curated_index import CuratedPage
from .curation_keys import DISCIPLINE_CONCEPT_TYPES, ENTITY_CONCEPT_TYPES, craft_concept_key, curated_id
from .curation_terms import write_curated_term_summaries
from .group_names import keep_proposed_group_name
from .structure_proposals_claims import ClaimPlan, write_curated_claim
from .structure_proposals_owner import (
    StructureOwner,
    owned_claim_ids,
    owner_page,
    proposal_owner,
    store_owner_page,
)
from .structure_proposals_page import (
    OwnerPage,
    PlacedEntry,
    entry_keys,
    entry_prefix,
    next_key,
    placed_page,
    subject_concept,
    target_problem,
)
from .structure_proposals_rows import stored_rows

__all__ = ["NO_CRAFT", "NO_PAGE", "STALE_STRUCTURE", "held_claims", "write_structure"]

STALE_STRUCTURE = "stale_structure"
NO_PAGE = "The page of this proposal no longer has a curated page to write it into."
NO_CRAFT = "The craft of this proposal is no longer held, so its name has no list to join."
MOVED_ON = "The page has moved on since this was proposed: {problem}."
OPEN_SENSITIVITY = "OPEN"
TERM_TYPE = ENTITY_CONCEPT_TYPES["TERM"]


@dataclass(frozen=True)
class _Written:
    claim_id: uuid.UUID | None
    concept_id: uuid.UUID | None
    page: OwnerPage


async def held_claims(session: AsyncSession, owner: StructureOwner) -> frozenset[uuid.UUID] | None:
    return await owned_claim_ids(session, owner) if owner.is_category else None


async def write_structure(session: AsyncSession, row: StructureProposal, reviewer: User) -> uuid.UUID | None:
    owner = await proposal_owner(session, row)
    item = parsed_item(row.item)
    if isinstance(item, GroupNameItem):
        if owner is None or owner.is_category:
            raise Refused(STALE_STRUCTURE, NO_CRAFT)
        await keep_proposed_group_name(session, owner.id, row, item)
        return None
    page = await owner_page(session, owner, lock=True) if owner is not None else None
    if owner is None or page is None:
        raise Refused(STALE_STRUCTURE, NO_PAGE)
    problem = target_problem(page, item, held=await held_claims(session, owner))
    if problem is not None:
        raise Refused(STALE_STRUCTURE, MOVED_ON.format(problem=problem))
    prefix = entry_prefix(item.kind)
    key = next_key(prefix, entry_keys(page, item.kind)) if prefix is not None else None
    written = await _claimed(session, owner, page, (row, item, key), reviewer)
    entry = PlacedEntry(written.claim_id, key, written.concept_id)
    rows = await stored_rows(session, owner, placed_page(written.page, item, entry), (item, entry))
    await store_owner_page(session, owner, rows.page)
    await _records(session, owner, item, written.claim_id)
    if rows.term_keys:
        await write_curated_term_summaries(session, keys=rows.term_keys)
    await session.flush()
    return written.claim_id


async def _claimed(
    session: AsyncSession,
    owner: StructureOwner,
    page: OwnerPage,
    proposed: tuple[StructureProposal, Any, str | None],
    reviewer: User,
) -> _Written:
    row, item, key = proposed
    if item.kind == CONFLICT:
        return _Written(claim_id=None, concept_id=None, page=page)
    concept_id, page = await _concept(session, owner, page, (item, key, row.field))
    plan = ClaimPlan(owner=owner, concept_id=concept_id, version=page.version, proposal=row)
    claim_id = await write_curated_claim(session, plan, reviewer)
    return _Written(claim_id=claim_id, concept_id=concept_id, page=page)


async def _concept(
    session: AsyncSession, owner: StructureOwner, page: OwnerPage, wanted: tuple[Any, str | None, str | None]
) -> tuple[uuid.UUID, OwnerPage]:
    item, key, field = wanted
    found = subject_concept(page, item, field)
    if found is not None:
        return found, page
    if item.kind == GLOSSARY_TERM and key is not None:
        concept_id = curated_id(owner.slug, "concept", key)
        await _insert_concept(session, owner, concept_id, (key, TERM_TYPE, item.term, item.meaning))
        return concept_id, page
    if field is None:
        raise Refused(STALE_STRUCTURE, NO_PAGE)
    concept_key = craft_concept_key(field)
    concept_id = curated_id(owner.slug, "concept", concept_key)
    await _insert_concept(
        session, owner, concept_id, (concept_key, DISCIPLINE_CONCEPT_TYPES[field], owner.name, None)
    )
    if not isinstance(page, CuratedPage):
        return concept_id, page
    concepts = {**page.craft_concepts, field: concept_id}
    return concept_id, page.model_copy(update={"craft_concepts": concepts})


async def _insert_concept(
    session: AsyncSession,
    owner: StructureOwner,
    concept_id: uuid.UUID,
    named: tuple[str, str, str, str | None],
) -> None:
    key, concept_type, name, description = named
    values = {
        "id": concept_id,
        "craftId": None if owner.is_category else owner.id,
        "subCategoryId": None,
        "type": concept_type,
        "name": name,
        "description": description,
        "originRef": f"curation:{owner.slug}:{key}",
        "sensitivity": OPEN_SENSITIVITY,
    }
    await session.execute(
        insert(Concept.__table__).values(values).on_conflict_do_nothing(index_elements=["id"])
    )


async def _records(
    session: AsyncSession, owner: StructureOwner, item: Any, claim_id: uuid.UUID | None
) -> None:
    if item.kind == CONFLICT:
        await session.execute(
            update(Claim)
            .where(Claim.id.in_(list(item.claim_ids)))
            .values(sourcesDiffer=True, differsOn=item.about)
        )
    if item.kind == GI_RECORD and claim_id is not None and not owner.is_category:
        await _gi(session, owner.id, item, claim_id)


async def _gi(session: AsyncSession, craft_id: uuid.UUID, item: GiRecordItem, claim_id: uuid.UUID) -> None:
    given = {column: value for column, value in _gi_columns(item).items() if value is not None}
    record = await session.get(CraftGiRecord, craft_id, with_for_update=True)
    if record is None:
        session.add(
            CraftGiRecord(craftId=craft_id, **given, proprietors=list(item.proprietors), claimIds=[claim_id])
        )
        return
    for column, value in given.items():
        setattr(record, column, value)
    record.proprietors = list(dict.fromkeys([*record.proprietors, *item.proprietors]))
    record.claimIds = list(dict.fromkeys([*record.claimIds, claim_id]))


def _gi_columns(item: GiRecordItem) -> dict[str, Any]:
    return {
        "applicationNumber": item.application_number,
        "certificateNumber": item.certificate_number,
        "filedOn": item.filed_on,
        "registeredOn": item.registered_on,
        "journalIssue": item.journal_issue,
        "authorisedUserCount": item.authorised_user_count,
    }
