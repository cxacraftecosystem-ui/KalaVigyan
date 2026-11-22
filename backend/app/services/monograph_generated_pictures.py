from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, ImageContribution, MediaAsset
from app.models.enums import DISCIPLINES
from app.research.chapter_keys import CHAPTER_KEYS
from app.research.component_specs import checked_spec
from app.research.coverage_chapters import field_chapter
from app.research.craft_contributed import contributed_credit, contributed_url
from app.research.image_contributions import AI_GENERATED
from app.research.image_intake_svg import SVG
from app.research.media_refs import MediaRef
from app.research.monograph_page import TextUnit
from app.research.page_layout import HERO_CHAPTER, PICTURE_ROLES, PageLayoutEntry

from .contributed_pictures import CONTRIBUTED_READ_MAX, shown_contributions
from .curated_index import IndexPicture
from .monograph_generated_units import MASTHEAD_CHAPTER
from .page_layouts_backfill import picture_placement

__all__ = [
    "PICTURE_KIND",
    "PlateSource",
    "contributed_plate",
    "contributed_plates",
    "curated_plate",
    "plate_spec",
    "plates_of",
]

KEY_PREFIX = "contributed-"
KEY_HEX_CHARS = 12
SLOT_PLACEMENTS: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "MASTHEAD": (HERO_CHAPTER, PICTURE_ROLES["MASTHEAD"]),
        "RECORD": (field_chapter("POLICY"), PICTURE_ROLES["RECORD"]),
    }
)
PICTURE_KIND = "picture_plate"
PLATE_CLASS = "plate"
PLATE_UNIT_PREFIX = "u"
PLATE_UNIT_START = 9001
STAGE_PLACEMENT = (field_chapter("PROCESS"), PICTURE_ROLES["STAGE"])
MATERIAL_PLACEMENT = (field_chapter("MATERIALS"), PICTURE_ROLES["MATERIAL"])
LOOSE_ROLE = PICTURE_ROLES["PLATE"]


@dataclass(frozen=True)
class PlateSource:
    key: str
    chapter: str
    role: str
    src: str
    width: int | None
    height: int | None
    alt: str
    caption: str
    credit: str
    attribution: str | None
    focal: Mapping[str, Any] | None = None
    facts: tuple[uuid.UUID, ...] = ()
    themed: bool = False

    def shown_with(self, visible: Collection[uuid.UUID]) -> bool:
        return all(fact in visible for fact in self.facts)


def plate_spec(
    source: PlateSource, entry: PageLayoutEntry | None, drawn: int
) -> tuple[dict[str, Any], dict[str, TextUnit]] | None:
    if source.width is None or source.height is None:
        return None
    caption_id, credit_id = (f"{PLATE_UNIT_PREFIX}{PLATE_UNIT_START + 2 * drawn + n}" for n in (0, 1))
    caption = entry.caption if entry is not None and entry.caption else source.caption
    units = {caption_id: _plain_unit(caption), credit_id: _plain_unit(source.credit)}
    crop = (
        entry.crop.model_dump(mode="json") if entry is not None and entry.crop is not None else source.focal
    )
    shown: dict[str, Any] = {
        "src": source.src,
        "width": source.width,
        "height": source.height,
        "alt": source.alt,
    }
    if crop is not None:
        shown["focal"] = dict(crop)
    if source.themed:
        shown["themed"] = True
    spec = {
        "setting": "figure",
        "picture": shown,
        "figure": {"classes": [PLATE_CLASS], "captions": [{"unit": caption_id}], "credit": credit_id},
    }
    try:
        checked = checked_spec(PICTURE_KIND, spec)
    except ValidationError:
        return None
    return checked.model_dump(mode="json", by_alias=True), units


def curated_plate(picture: IndexPicture, media: MediaRef) -> PlateSource:
    chapter, role = picture_placement(picture)
    named = ", ".join(part for part in (media.author, media.licence) if part)
    return PlateSource(
        key=picture.key,
        chapter=chapter,
        role=role,
        src=str(media.image_url),
        width=media.width,
        height=media.height,
        alt=media.alt,
        caption=picture.caption,
        credit=f"Photo: {named}, via {media.site}" if named else f"Photo: {media.site}",
        attribution=named or None,
        focal=picture.focal.model_dump(mode="json") if picture.focal is not None else None,
    )


async def contributed_plates(session: AsyncSession, craft_id: uuid.UUID) -> list[PlateSource]:
    rows = (
        await session.execute(
            select(ImageContribution, MediaAsset)
            .join(MediaAsset, MediaAsset.id == ImageContribution.assetId)
            .where(ImageContribution.id.in_(shown_contributions(craft_id)))
            .order_by(ImageContribution.reviewedAt, ImageContribution.id)
            .limit(CONTRIBUTED_READ_MAX)
        )
    ).all()
    return await plates_of(session, [(row, asset) for row, asset in rows], contributed_url)


async def plates_of(
    session: AsyncSession,
    rows: Sequence[tuple[ImageContribution, MediaAsset]],
    address: Callable[[uuid.UUID], str],
) -> list[PlateSource]:
    fields = await _fact_fields(session, [claim for row, _ in rows for claim in row.claimIds])
    return [contributed_plate(row, asset, address(row.id), _placement(row, fields)) for row, asset in rows]


def contributed_plate(
    row: ImageContribution, asset: MediaAsset, src: str, placed: tuple[str, str]
) -> PlateSource:
    ai = row.origin == AI_GENERATED
    credit = contributed_credit(row.origin, row.generator if ai else None)
    return PlateSource(
        key=f"{KEY_PREFIX}{row.id.hex[:KEY_HEX_CHARS]}",
        chapter=placed[0],
        role=placed[1],
        src=src,
        width=asset.width,
        height=asset.height,
        alt=row.altText,
        caption=row.caption,
        credit=credit,
        attribution=credit,
        facts=tuple(row.claimIds) if ai else (),
        themed=asset.mime == SVG,
    )


def _placement(row: ImageContribution, fields: Mapping[uuid.UUID, str]) -> tuple[str, str]:
    if row.slot is not None and row.slot in SLOT_PLACEMENTS:
        return SLOT_PLACEMENTS[row.slot]
    if row.stageId is not None:
        return STAGE_PLACEMENT
    if row.materialId is not None:
        return MATERIAL_PLACEMENT
    counted = Counter(
        field_chapter(fields[claim]) for claim in dict.fromkeys(row.claimIds) if claim in fields
    )
    if not counted:
        return HERO_CHAPTER, LOOSE_ROLE
    return min(counted, key=lambda chapter: (-counted[chapter], CHAPTER_KEYS.index(chapter))), LOOSE_ROLE


def _plain_unit(text: str) -> TextUnit:
    return TextUnit(chapter=MASTHEAD_CHAPTER, tag="span", field=None, nodes=[text], claim_ids=[])


async def _fact_fields(session: AsyncSession, claim_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not claim_ids:
        return {}
    rows = await session.execute(select(Claim.id, Claim.field).where(Claim.id.in_(list(set(claim_ids)))))
    return {claim_id: field for claim_id, field in rows.all() if field in DISCIPLINES}
