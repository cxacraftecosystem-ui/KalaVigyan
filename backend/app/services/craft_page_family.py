from __future__ import annotations

import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.craft_families import CraftKind, FamilyPlace, load_craft_families
from app.data.craft_names import load_craft_names
from app.models import Craft, CuratedCraft
from app.models.enums import COVERAGE_CLASSES
from app.research.blocks import ProseBlock
from app.research.citations import SourceRef
from app.research.craft_page_context import SAME_FAMILY_MAX, HeroImage, PageRelative, RelativeLede
from app.research.crafts import CraftRef
from app.research.knowledge_pieces import KnowledgePiece
from app.research.media_refs import MediaRef

from . import knowledge_view
from .claim_holds import unheld_by_id
from .craft_claim_counts import craft_claim_counts
from .curated_index import CuratedPage, stored_curated_page
from .media_ref_store import stored_media_refs
from .piece_lookup import stored_pieces

__all__ = [
    "FamilyCandidate",
    "RelativeExtras",
    "ShownPicture",
    "depth_basis",
    "display_name",
    "family_place",
    "family_relatives",
    "hero_index",
    "masthead_index",
    "page_relative",
    "ranked_family",
    "reader_name",
    "relative_extras",
    "shown_pictures",
    "suggested_questions",
]

ACTIVE = "ACTIVE"
GI = "GI"
INLINE = "INLINE"
MASTHEAD = "MASTHEAD"
COVERAGE_RANK = MappingProxyType({coverage: rank for rank, coverage in enumerate(COVERAGE_CLASSES)})


@dataclass(frozen=True)
class FamilyCandidate:
    craft: CraftRef
    gi_status: str | None
    state_of_practice: tuple[str, ...]
    coverage: str | None
    claims: int
    catch_all: bool = False


@dataclass(frozen=True)
class RelativeExtras:
    hero: HeroImage | None = None
    lede: RelativeLede | None = None


@dataclass(frozen=True)
class ShownPicture:
    media: MediaRef
    caption: str
    stage_id: uuid.UUID | None
    claim_ids: list[uuid.UUID]
    placed_as: str | None = None


def family_place(category_name: str | None, sub_category_name: str | None) -> FamilyPlace:
    return load_craft_families().place_of(category_name, sub_category_name)


def display_name(name: str, *, catch_all: bool, kind: CraftKind | None) -> str:
    return kind.other_name if catch_all and kind is not None else name


def reader_name(slug: str, name: str, *, catch_all: bool, kind: CraftKind | None) -> str:
    return display_name(load_craft_names().display_name(slug, name), catch_all=catch_all, kind=kind)


def suggested_questions(place: FamilyPlace, name: str, *, catch_all: bool) -> list[str]:
    if catch_all and place.kind is not None:
        return list(place.kind.other_questions)
    return load_craft_families().questions(place, name)


def depth_basis(coverage: str | None, claims: int) -> str:
    if coverage is not None:
        return "CURATED"
    return "STORED_CLAIMS" if claims else "REGISTER"


def ranked_family(candidates: Sequence[FamilyCandidate], *, own_slug: str) -> list[FamilyCandidate]:
    eligible = [item for item in candidates if item.craft.slug != own_slug and not item.catch_all]
    return sorted(eligible, key=_richness)[:SAME_FAMILY_MAX]


def page_relative(candidate: FamilyCandidate, extras: RelativeExtras | None = None) -> PageRelative:
    found = extras or RelativeExtras()
    return PageRelative(
        craft=candidate.craft,
        display_name=reader_name(candidate.craft.slug, candidate.craft.name, catch_all=False, kind=None),
        gi_status=candidate.gi_status,
        state_of_practice=list(candidate.state_of_practice),
        basis=depth_basis(candidate.coverage, candidate.claims),
        coverage=candidate.coverage,
        claims=candidate.claims,
        hero=found.hero,
        lede=found.lede,
    )


def hero_index(pictures: Sequence[tuple[MediaRef, object]], *, masthead: int | None = None) -> int | None:
    if masthead is not None and pictures[masthead][0].display == INLINE:
        return masthead
    inline = [index for index, (media, _stage) in enumerate(pictures) if media.display == INLINE]
    unstaged = [index for index in inline if pictures[index][1] is None]
    return (unstaged or inline or [None])[0]


def masthead_index(placements: Sequence[str | None]) -> int | None:
    return next((index for index, role in enumerate(placements) if role == MASTHEAD), None)


def shown_pictures(
    curated: CuratedPage, media: Mapping[uuid.UUID, MediaRef], visible: Collection[uuid.UUID]
) -> list[ShownPicture]:
    stages = {stage.key: stage.stage_id for stage in curated.stages}
    shown = []
    for picture in curated.pictures:
        found = media.get(picture.media_ref_id)
        claims = [claim_id for claim_id in dict.fromkeys(picture.claim_ids) if claim_id in visible]
        stage = stages.get(picture.stage_key) if picture.stage_key else None
        role = picture.placement.role if picture.placement else None
        if found is not None and (claims or stage):
            shown.append(ShownPicture(found, picture.caption, stage, claims, role))
    return shown


def relative_extras(
    curated: CuratedPage,
    media: Mapping[uuid.UUID, MediaRef],
    lede: KnowledgePiece | None,
    cited: tuple[Collection[uuid.UUID], Mapping[str, SourceRef]],
) -> RelativeExtras:
    shown = shown_pictures(curated, media, cited[0])
    masthead = masthead_index([picture.placed_as for picture in shown])
    chosen = hero_index([(picture.media, picture.stage_id) for picture in shown], masthead=masthead)
    hero = None if chosen is None else HeroImage(media=shown[chosen].media, caption=shown[chosen].caption)
    return RelativeExtras(hero=hero, lede=_first_lede(lede, *cited))


async def family_relatives(session: AsyncSession, craft: Craft, *, mode: str) -> tuple[PageRelative, ...]:
    if craft.subCategoryId is None:
        return ()
    columns = (Craft.id, Craft.slug, Craft.name, Craft.giStatus, Craft.stateOfPractice, Craft.isCatchAll)
    rows = (
        await session.execute(
            select(*columns, CuratedCraft.coverage)
            .outerjoin(CuratedCraft, CuratedCraft.craftId == Craft.id)
            .where(Craft.subCategoryId == craft.subCategoryId, Craft.status == ACTIVE, Craft.id != craft.id)
        )
    ).all()
    ids = {row.slug: row.id for row in rows}
    counts = await craft_claim_counts(session, list(ids.values()), mode=mode)
    candidates = [_candidate(row, counts.get(row.id, 0)) for row in rows]
    chosen = ranked_family(candidates, own_slug=craft.slug)
    extras = await _curated_extras(session, [ids[item.craft.slug] for item in chosen if item.coverage])
    return tuple(page_relative(item, extras.get(ids[item.craft.slug])) for item in chosen)


def _richness(candidate: FamilyCandidate) -> tuple[int, int, bool, str, str]:
    return (
        COVERAGE_RANK.get(candidate.coverage or "", len(COVERAGE_RANK)),
        -candidate.claims,
        candidate.gi_status != GI,
        candidate.craft.name.casefold(),
        candidate.craft.slug,
    )


def _candidate(row: Any, claims: int) -> FamilyCandidate:
    return FamilyCandidate(
        craft=CraftRef(slug=row.slug, name=row.name, path=f"/crafts/{row.slug}"),
        gi_status=row.giStatus,
        state_of_practice=tuple(row.stateOfPractice or ()),
        coverage=row.coverage,
        claims=claims,
        catch_all=bool(row.isCatchAll),
    )


def _first_lede(
    piece: KnowledgePiece | None, visible: Collection[uuid.UUID], sources: Mapping[str, SourceRef]
) -> RelativeLede | None:
    if piece is None or not isinstance(piece.payload, ProseBlock):
        return None
    for sentence in piece.payload.sentences:
        claims = {uuid.UUID(citation.claim_id) for citation in sentence.citations}
        cited = list(dict.fromkeys(citation.source_id for citation in sentence.citations))
        if claims <= set(visible) and all(source_id in sources for source_id in cited):
            return RelativeLede(
                text=sentence.text,
                citations=list(sentence.citations),
                sources=[sources[source_id] for source_id in cited],
            )
    return None


async def _curated_extras(
    session: AsyncSession, craft_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, RelativeExtras]:
    if not craft_ids:
        return {}
    statement = select(CuratedCraft.craftId, CuratedCraft.page).where(CuratedCraft.craftId.in_(craft_ids))
    found = (
        (row[0], stored_curated_page(row[0], row[1])) for row in (await session.execute(statement)).all()
    )
    pages = {craft_id: page for craft_id, page in found if page is not None}
    media = await stored_media_refs(
        session, [picture.media_ref_id for page in pages.values() for picture in page.pictures]
    )
    ledes = {craft_id: page.overview.lede_piece_id for craft_id, page in pages.items()}
    pieces = await stored_pieces(session, [piece_id for piece_id in ledes.values() if piece_id])
    pictured = [claim_id for page in pages.values() for item in page.pictures for claim_id in item.claim_ids]
    cited = await _cited(session, pieces.values(), pictured)
    return {
        craft_id: relative_extras(
            page, media, pieces.get(ledes[craft_id]) if ledes[craft_id] else None, cited
        )
        for craft_id, page in pages.items()
    }


async def _cited(
    session: AsyncSession, pieces: Collection[KnowledgePiece], pictured: Sequence[uuid.UUID]
) -> tuple[set[uuid.UUID], dict[str, SourceRef]]:
    claim_ids = [
        uuid.UUID(citation.claim_id)
        for piece in pieces
        if isinstance(piece.payload, ProseBlock)
        for sentence in piece.payload.sentences
        for citation in sentence.citations
    ]
    views, sources = await knowledge_view.claims_by_id(session, [*claim_ids, *pictured])
    views = await unheld_by_id(session, views)
    refs = {
        str(key): SourceRef.model_validate(knowledge_view.source_ref(row)) for key, row in sources.items()
    }
    return set(views), refs
