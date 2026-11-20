from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.research.monograph_document import MonographDocument

from . import knowledge_view
from .coverage import coverage_of
from .document_components_store import subject_structure
from .monograph_generated_assembly import GeneratedParts, assembled_document
from .monograph_generated_drawings import Drawings
from .monograph_generated_grids import stated_values
from .monograph_generated_parts import subject_components, subject_pictures, subject_record, subject_sections
from .monograph_generated_structure import structure_claim_ids, with_page_claims
from .monograph_generated_units import stored_source
from .open_work_subjects import WorkSubject, subject_by_key
from .page_layouts import layout_of, subject_path

__all__ = ["CRAFT_SECTIONS_MIN", "enough_sections", "generated_document", "generated_parts", "page_url"]

CRAFT_SECTIONS_MIN = 3
CRAFT = "craft"


def enough_sections(subject_kind: str, published: int) -> bool:
    return subject_kind != CRAFT or published >= CRAFT_SECTIONS_MIN


async def generated_document(session: AsyncSession, subject_kind: str, slug: str) -> MonographDocument | None:
    parts = await generated_parts(session, await subject_by_key(session, subject_kind, slug))
    return None if parts is None else assembled_document(parts, Drawings())


async def generated_parts(session: AsyncSession, subject: WorkSubject) -> GeneratedParts | None:
    stored = await subject_sections(session, subject)
    if not enough_sections(subject.kind, len(stored)):
        return None
    structure = await subject_structure(session, subject)
    sections = with_page_claims(stored, structure)
    claim_ids = [
        uuid.UUID(str(claim))
        for section in sections
        for sentence in section.sentences
        for claim in sentence["claimIds"]
    ]
    if not claim_ids:
        return None
    visible, rows = await knowledge_view.claims_by_id(session, [*claim_ids, *structure_claim_ids(structure)])
    if not visible:
        return None
    return GeneratedParts(
        subject_kind=subject.kind,
        subject_slug=subject.slug,
        page_url=page_url(subject),
        record=await subject_record(session, subject),
        sections=tuple(sections),
        visible=visible,
        sources={str(key): stored_source(knowledge_view.source_ref(row)) for key, row in rows.items()},
        components=tuple(await subject_components(session, subject, list(visible))),
        pictures=tuple(await subject_pictures(session, subject)),
        layout=await layout_of(session, subject),
        coverage=await coverage_of(session, subject),
        values=await stated_values(session, list(visible)),
        structure=structure,
    )


def page_url(subject: WorkSubject) -> str:
    return f"{get_settings().public_web_url.rstrip('/')}{subject_path(subject)}"
