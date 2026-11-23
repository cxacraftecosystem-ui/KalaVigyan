from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Source
from app.research.monograph_document import MonographDocument

from . import knowledge_view
from .claim_holds import unheld_by_id
from .component_places_held import subject_places
from .component_proposals_drawn import with_delivered_claims
from .coverage import coverage_of
from .craft_page_unwritten import unwritten_facts, with_listed_fields
from .document_components_store import subject_structure
from .knowledge_view import ClaimView
from .monograph_generated_assembly import GeneratedParts, assembled_document
from .monograph_generated_drawings import Drawings
from .monograph_generated_grids import stated_values
from .monograph_generated_kin import subject_kin
from .monograph_generated_parts import (
    StoredSection,
    subject_components,
    subject_pictures,
    subject_record,
    subject_sections,
)
from .monograph_generated_structure import shown_claim_ids, structure_claim_ids, with_page_claims
from .monograph_generated_units import stored_source
from .open_work_subjects import WorkSubject, subject_by_key
from .page_layouts import layout_of, subject_path
from .page_preview_additions import NO_ADDITIONS, PageAdditions
from .place_ground import subject_ground

__all__ = [
    "CRAFT_SECTIONS_MIN",
    "enough_sections",
    "generated_document",
    "generated_document_of",
    "generated_parts",
    "page_url",
]

CRAFT_SECTIONS_MIN = 3
CRAFT = "craft"


def enough_sections(subject_kind: str, published: int) -> bool:
    return subject_kind != CRAFT or published >= CRAFT_SECTIONS_MIN


async def generated_document(session: AsyncSession, subject_kind: str, slug: str) -> MonographDocument | None:
    return await generated_document_of(session, await subject_by_key(session, subject_kind, slug))


async def generated_document_of(session: AsyncSession, subject: WorkSubject) -> MonographDocument | None:
    parts = await generated_parts(session, subject)
    return None if parts is None else assembled_document(parts, Drawings())


async def generated_parts(
    session: AsyncSession, subject: WorkSubject, additions: PageAdditions = NO_ADDITIONS
) -> GeneratedParts | None:
    stored = additions.sections(await subject_sections(session, subject))
    if not enough_sections(subject.kind, len(stored)):
        return None
    structure = await subject_structure(session, subject)
    unwritten = await unwritten_facts(session, subject, shown_claim_ids(stored, structure))
    sections = with_page_claims(stored, structure, listed=unwritten.views().keys())
    written = [*_sentence_claims(sections), *structure_claim_ids(structure)]
    found = await _written_views(session, sections, written, additions)
    if found is None:
        return None
    components = additions.components(await subject_components(session, subject, list(found[0])))
    visible, rows = await with_delivered_claims(session, components, *found)
    visible, rows = {**visible, **unwritten.views()}, {**rows, **unwritten.sources}
    sources = {str(key): stored_source(knowledge_view.source_ref(row)) for key, row in rows.items()}
    record = await subject_record(session, subject)
    kin = await subject_kin(session, subject, record.kicker)
    return GeneratedParts(
        subject_kind=subject.kind,
        subject_slug=subject.slug,
        page_url=page_url(subject),
        record=record,
        sections=tuple(with_listed_fields(sections, unwritten.by_field)),
        visible={**kin.visible, **visible},
        sources={**kin.sources, **sources, **additions.sources},
        components=components,
        pictures=additions.pictures(await subject_pictures(session, subject)),
        layout=additions.layout if additions.layout is not None else await layout_of(session, subject),
        coverage=await coverage_of(session, subject),
        values=await stated_values(session, list(visible)),
        structure=structure,
        places=await subject_places(session, subject),
        ground=await subject_ground(session, subject.id) if subject.kind == CRAFT else None,
        unwritten=unwritten.by_field,
        kin=kin,
    )


async def _written_views(
    session: AsyncSession,
    sections: Sequence[StoredSection],
    written: Sequence[uuid.UUID],
    additions: PageAdditions,
) -> tuple[dict[uuid.UUID, ClaimView], dict[uuid.UUID, Source]] | None:
    if not _sentence_claims(sections):
        return None
    looked_up = [claim for claim in written if claim not in additions.claims]
    visible, rows = await knowledge_view.claims_by_id(session, looked_up)
    visible = {**await unheld_by_id(session, visible), **additions.claims}
    return (visible, rows) if visible else None


def _sentence_claims(sections: Sequence[StoredSection]) -> list[uuid.UUID]:
    return [
        uuid.UUID(str(claim)) for section in sections for s in section.sentences for claim in s["claimIds"]
    ]


def page_url(subject: WorkSubject) -> str:
    return f"{get_settings().public_web_url.rstrip('/')}{subject_path(subject)}"
