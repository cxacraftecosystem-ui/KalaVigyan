from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import KnowledgePiece, Source
from app.research.blocks_component import COMPONENT_KIND, ComponentBlock, ComponentSource, component_href
from app.research.composition import COMPONENTS_OFFERED_MAX, ComponentOption
from app.research.crafts import CraftRef
from app.research.knowledge_api import ComponentSummary
from app.research.planning import PlanRequest
from app.research.retrieval import RESTRICTED_SENSITIVITY
from app.research.sections import block_id

from . import knowledge_view
from .answer_events import CitedClaims
from .component_library import library_components

__all__ = [
    "NO_CATALOGUE",
    "CatalogueEntry",
    "CatalogueLookup",
    "PlacedComponents",
    "SectionCatalogue",
    "catalogue_lookup",
    "no_catalogue",
    "section_catalogue",
]

logger = logging.getLogger(__name__)

MONOGRAPH_KEY = "monograph"
ANCHOR_KEY = "anchor"
PROBE_SECTION = "s1"

SourceRefs = Mapping[str, Mapping[str, Any]]


@dataclass(frozen=True)
class CatalogueEntry:
    label: str
    kind: str
    title: str
    description: str
    craft: CraftRef
    anchor: str
    sources: SourceRefs

    def option(self) -> ComponentOption:
        return ComponentOption(label=self.label, kind=self.kind, description=self.description)

    def block(self, placed_id: str) -> ComponentBlock:
        return ComponentBlock(
            id=placed_id,
            kind=COMPONENT_KIND,
            version=1,
            reuse=None,
            label=self.label,
            component_kind=self.kind,
            title=self.title,
            craft=self.craft,
            href=component_href(self.craft, self.anchor),
            sources=[ComponentSource(source_id=source_id) for source_id in self.sources],
        )


@dataclass(frozen=True)
class PlacedComponents:
    blocks: tuple[ComponentBlock, ...] = ()
    cited: CitedClaims = field(default_factory=CitedClaims)


@dataclass(frozen=True)
class SectionCatalogue:
    entries: tuple[CatalogueEntry, ...] = ()

    def options(self) -> list[ComponentOption]:
        return [entry.option() for entry in self.entries]

    def placed(self, labels: Sequence[str], *, section_id: str, first: int) -> PlacedComponents:
        offered = {entry.label: entry for entry in self.entries}
        chosen = [offered[label] for label in dict.fromkeys(labels) if label in offered]
        blocks = tuple(entry.block(block_id(section_id, first + n)) for n, entry in enumerate(chosen))
        sources = {source_id: dict(ref) for entry in chosen for source_id, ref in entry.sources.items()}
        return PlacedComponents(blocks, CitedClaims(sources=sources))


NO_CATALOGUE = SectionCatalogue()

CatalogueLookup = Callable[[PlanRequest, str], Awaitable[SectionCatalogue]]


async def no_catalogue(request: PlanRequest, field: str) -> SectionCatalogue:
    return NO_CATALOGUE


def catalogue_lookup(sessions: async_sessionmaker[AsyncSession]) -> CatalogueLookup:
    async def lookup(request: PlanRequest, field: str) -> SectionCatalogue:
        craft = request.craft
        if craft is None:
            return NO_CATALOGUE
        words = request.english_question or request.question
        try:
            async with sessions() as session:
                return await section_catalogue(session, craft_slug=craft.slug, field=field, question=words)
        except SQLAlchemyError, OSError:
            logger.warning(
                "the component catalogue of %s for %s failed; the section offers none",
                craft.slug,
                field,
                exc_info=True,
            )
            return NO_CATALOGUE

    return lookup


async def section_catalogue(
    session: AsyncSession, *, craft_slug: str, field: str, question: str
) -> SectionCatalogue:
    summaries = (await library_components(session, slug=craft_slug, field=field, query=question)).components
    if not summaries:
        return NO_CATALOGUE
    pieces = await _pieces(session, [summary.label for summary in summaries])
    pages = await _pages(session, (piece.payload.get(MONOGRAPH_KEY) for piece in pieces.values()))
    sources = await _sources(
        session, (source_id for piece in pieces.values() for source_id in piece.sourceIds)
    )
    entries = (_entry(summary, pieces.get(summary.label), pages, sources) for summary in summaries)
    return SectionCatalogue(tuple(entry for entry in entries if entry is not None)[:COMPONENTS_OFFERED_MAX])


async def _pieces(session: AsyncSession, labels: Sequence[str]) -> dict[str, KnowledgePiece]:
    rows = await session.scalars(select(KnowledgePiece).where(KnowledgePiece.label.in_(list(labels))))
    return {str(piece.label): piece for piece in rows}


async def _pages(session: AsyncSession, slugs: Iterable[Any]) -> dict[str, CraftRef]:
    pages: dict[str, CraftRef] = {}
    for slug in dict.fromkeys(slug for slug in slugs if isinstance(slug, str) and slug):
        craft = await knowledge_view.resolve_craft(session, slug)
        if craft is not None:
            pages[slug] = CraftRef.model_validate(knowledge_view.craft_ref(craft))
    return pages


async def _sources(session: AsyncSession, source_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    ids = [parsed for source_id in dict.fromkeys(source_ids) if (parsed := _uuid(source_id)) is not None]
    if not ids:
        return {}
    rows = await session.scalars(
        select(Source).where(Source.id.in_(ids), Source.sensitivity != RESTRICTED_SENSITIVITY)
    )
    return {str(source.id): knowledge_view.source_ref(source) for source in rows}


def _entry(
    summary: ComponentSummary,
    piece: KnowledgePiece | None,
    pages: Mapping[str, CraftRef],
    sources: Mapping[str, Mapping[str, Any]],
) -> CatalogueEntry | None:
    payload: Mapping[str, Any] = piece.payload if piece is not None else {}
    page = pages.get(str(payload.get(MONOGRAPH_KEY)))
    rests_on = list(piece.sourceIds) if piece is not None else []
    if page is None or not rests_on or any(source_id not in sources for source_id in rests_on):
        logger.warning(
            "component %s names no page or source a reader can open; it is not offered", summary.label
        )
        return None
    entry = CatalogueEntry(
        label=summary.label,
        kind=summary.kind,
        title=summary.title,
        description=summary.description,
        craft=page,
        anchor=str(payload.get(ANCHOR_KEY) or ""),
        sources={source_id: sources[source_id] for source_id in rests_on},
    )
    return entry if _placeable(entry) else None


def _placeable(entry: CatalogueEntry) -> bool:
    try:
        entry.option()
        entry.block(block_id(PROBE_SECTION, 1))
    except ValidationError as refused:
        logger.warning(
            "component %s cannot be placed (%d problems); it is not offered",
            entry.label,
            refused.error_count(),
        )
        return False
    return True


def _uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
