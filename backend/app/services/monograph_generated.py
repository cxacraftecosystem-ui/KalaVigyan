from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.research.monograph_document import MonographDocument

from . import knowledge_view
from .claim_holds import unheld_by_id
from .component_proposals_drawn import with_delivered_claims
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
from .page_preview_additions import NO_ADDITIONS, PageAdditions

__all__ = ["CRAFT_SECTIONS_MIN", "enough_sections", "generated_document", "generated_parts", "page_url"]

CRAFT_SECTIONS_MIN = 3
CRAFT = "craft"


def enough_sections(subject_kind: str, published: int) -> bool:
    return subject_kind != CRAFT or published >= CRAFT_SECTIONS_MIN


async def generated_document(session: AsyncSession, subject_kind: str, slug: str) -> MonographDocument | None:
    parts = await generated_parts(session, await subject_by_key(session, subject_kind, slug))
    return None if parts is None else assembled_document(parts, Drawings())


async def generated_parts(
    session: AsyncSession, subject: WorkSubject, additions: PageAdditions = NO_ADDITIONS
) -> GeneratedParts | None:
    stored = additions.sections(await subject_sections(session, subject))
    if not enough_sections(subject.kind, len(stored)):
        return None
    structure = await subject_structure(session, subject)
    sections = with_page_claims(stored, structure)
    claim_ids = [
        uuid.UUID(str(claim)) for section in sections for s in section.sentences for claim in s["claimIds"]
    ]
    if not claim_ids:
        return None
    looked_up = [
        claim for claim in [*claim_ids, *structure_claim_ids(structure)] if claim not in additions.claims
    ]
    visible, rows = await knowledge_view.claims_by_id(session, looked_up)
    visible = await unheld_by_id(session, visible)
    visible = {**visible, **additions.claims}
    if not visible:
        return None
    components = additions.components(await subject_components(session, subject, list(visible)))
    visible, rows = await with_delivered_claims(session, components, visible, rows)
    sources = {str(key): stored_source(knowledge_view.source_ref(row)) for key, row in rows.items()}
    return GeneratedParts(
        subject_kind=subject.kind,
        subject_slug=subject.slug,
        page_url=page_url(subject),
        record=await subject_record(session, subject),
        sections=tuple(sections),
        visible=visible,
        sources={**sources, **additions.sources},
        components=components,
        pictures=additions.pictures(await subject_pictures(session, subject)),
        layout=additions.layout if additions.layout is not None else await layout_of(session, subject),
        coverage=await coverage_of(session, subject),
        values=await stated_values(session, list(visible)),
        structure=structure,
    )


def page_url(subject: WorkSubject) -> str:
    return f"{get_settings().public_web_url.rstrip('/')}{subject_path(subject)}"
