from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import MappingProxyType

from app.core.config import get_settings
from app.research.blocks_play import hidden_block
from app.research.citation_export import CitationExport
from app.research.citation_formats import (
    ApaReferences,
    CitedThing,
    citation_entries,
    cited_datasets,
    exported_citations,
)
from app.research.explainer import explainer_blocks
from app.research.explainer_versions import ExplainerVersionDocument
from app.research.export_links import ExportLink
from app.research.export_text import References
from app.research.lesson_builder import first_picture
from app.research.lessons import LessonPack
from app.research.media_refs import MediaRef
from app.sources.http import source_client
from app.sources.images.picture_files import picture_files

from .apa_references import apa_references
from .export_pictures import Picture, PictureSource, export_pictures
from .export_store import BuiltExport, ExportFile, ExportObjects, stored_export_link
from .lesson_deck import lesson_deck
from .naming import explainer_file_name, lesson_file_name

__all__ = [
    "REPORT_WHAT",
    "ExportTools",
    "explainer_citations",
    "explainer_cited",
    "explainer_pdf_link",
    "lesson_file_link",
    "opened_export_tools",
]

REPORT_WHAT = "Report"
PDF = "pdf"

LessonRenderer = Callable[[LessonPack, References, Mapping[uuid.UUID, Picture]], bytes]


def _slides(pack: LessonPack, refs: References, pictures: Mapping[uuid.UUID, Picture]) -> bytes:
    from .lesson_pptx import lesson_pptx

    return lesson_pptx(pack, refs, pictures)


def _handout(pack: LessonPack, refs: References, pictures: Mapping[uuid.UUID, Picture]) -> bytes:
    from .export_pdfs import lesson_pdf

    return lesson_pdf(pack, refs, pictures)


def _report(
    document: ExplainerVersionDocument, refs: References, pictures: Mapping[uuid.UUID, Picture]
) -> bytes:
    from .export_pdfs import explainer_pdf

    return explainer_pdf(document, refs, pictures)


LESSON_RENDERERS: Mapping[str, LessonRenderer] = MappingProxyType(
    {"html": lesson_deck, "pptx": _slides, "pdf": _handout}
)


@dataclass(frozen=True)
class ExportTools:
    objects: ExportObjects
    pictures: PictureSource
    apa: ApaReferences
    clock: Callable[[], datetime]
    builds: asyncio.Semaphore


@asynccontextmanager
async def opened_export_tools(
    objects: ExportObjects, builds: asyncio.Semaphore
) -> AsyncIterator[ExportTools]:
    async with source_client(get_settings().research_contact_email) as client:
        yield ExportTools(
            objects=objects,
            pictures=picture_files(client),
            apa=apa_references,
            clock=lambda: datetime.now(UTC),
            builds=builds,
        )


def explainer_cited(document: ExplainerVersionDocument) -> list[CitedThing]:
    explainer = document.explainer
    shown = [block for block in explainer_blocks(explainer) if not hidden_block(block)]
    cited = {source_id for block in shown for source_id in block.cited_source_ids()}
    return [*(source for source in explainer.sources if source.id in cited), *cited_datasets(shown)]


def explainer_citations(
    document: ExplainerVersionDocument, accessed: Mapping[str, date], apa: ApaReferences
) -> CitationExport:
    entries = citation_entries(explainer_cited(document), accessed=accessed, apa=apa)
    return exported_citations(document.mark.explainer_id, document.mark.version, entries)


async def lesson_file_link(
    tools: ExportTools, owner_id: uuid.UUID, pack: LessonPack, accessed: Mapping[str, date], fmt: str
) -> ExportLink:
    render = LESSON_RENDERERS[fmt]
    name = lesson_file_name(
        made_at=pack.created_at, craft=pack.craft.name if pack.craft else None, title=pack.title, fmt=fmt
    )
    made_from = {"pack": pack.model_dump(mode="json", by_alias=True), "accessed": _iso(accessed)}

    def written(pictures: Mapping[uuid.UUID, Picture]) -> bytes:
        refs = References(tuple(citation_entries(pack.sources, accessed=accessed, apa=tools.apa)))
        return render(pack, refs, pictures)

    async def build() -> BuiltExport:
        pictures = await export_pictures(_pictures_of(pack), tools.pictures)
        return BuiltExport(await asyncio.to_thread(written, pictures.found), pictures.unread)

    export = ExportFile(owner_id=owner_id, fmt=fmt, file_name=name, made_from=made_from)
    return await stored_export_link(tools.objects, export, build, now=tools.clock(), builds=tools.builds)


async def explainer_pdf_link(
    tools: ExportTools, owner_id: uuid.UUID, document: ExplainerVersionDocument, accessed: Mapping[str, date]
) -> ExportLink:
    explainer = document.explainer
    crafts = explainer.understood.crafts
    name = explainer_file_name(
        made_at=document.mark.created_at,
        craft=crafts[0].name if crafts else None,
        question=document.mark.question,
        version=document.mark.version,
        what=REPORT_WHAT,
        ext=PDF,
    )
    made_from = {"explainer": document.model_dump(mode="json", by_alias=True), "accessed": _iso(accessed)}

    def written(pictures: Mapping[uuid.UUID, Picture]) -> bytes:
        refs = References(tuple(explainer_citations(document, accessed, tools.apa).entries))
        return _report(document, refs, pictures)

    async def build() -> BuiltExport:
        pictures = await export_pictures(_explainer_pictures(document), tools.pictures)
        return BuiltExport(await asyncio.to_thread(written, pictures.found), pictures.unread)

    export = ExportFile(owner_id=owner_id, fmt=PDF, file_name=name, made_from=made_from)
    return await stored_export_link(tools.objects, export, build, now=tools.clock(), builds=tools.builds)


def _pictures_of(pack: LessonPack) -> list[MediaRef]:
    return [slide.image for slide in pack.slides if slide.image is not None]


def _explainer_pictures(document: ExplainerVersionDocument) -> list[MediaRef]:
    found = (first_picture(section) for section in document.explainer.sections)
    return [media for media in found if media is not None]


def _iso(accessed: Mapping[str, date]) -> dict[str, str]:
    return {key: day.isoformat() for key, day in sorted(accessed.items())}
