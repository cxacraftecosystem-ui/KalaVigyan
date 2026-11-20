from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .image_contributions import PICTURE_SLOTS

__all__ = [
    "CRAFT_SUBJECT",
    "PICTURE_TASK",
    "SLOT_DETAILS",
    "PictureAim",
    "is_picture_detail",
    "picture_aim",
    "picture_detail",
]

PICTURE_TASK = "MISSING_PICTURE"
CRAFT_SUBJECT = "craft"
STAGE_PREFIX = "stage-"
MATERIAL_PREFIX = "material-"
SLOT_DETAILS: Mapping[str, str] = MappingProxyType({slot: f"slot-{slot.lower()}" for slot in PICTURE_SLOTS})
SLOTS_BY_DETAIL: Mapping[str, str] = MappingProxyType({detail: slot for slot, detail in SLOT_DETAILS.items()})


@dataclass(frozen=True)
class PictureAim:
    stage_id: uuid.UUID | None = None
    material_id: uuid.UUID | None = None
    slot: str | None = None


def picture_detail(aim: PictureAim) -> str | None:
    if aim.stage_id is not None:
        return f"{STAGE_PREFIX}{aim.stage_id}"
    if aim.material_id is not None:
        return f"{MATERIAL_PREFIX}{aim.material_id}"
    return SLOT_DETAILS.get(aim.slot) if aim.slot is not None else None


def picture_aim(detail: str) -> PictureAim | None:
    if detail in SLOTS_BY_DETAIL:
        return PictureAim(slot=SLOTS_BY_DETAIL[detail])
    for prefix, field in ((STAGE_PREFIX, "stage_id"), (MATERIAL_PREFIX, "material_id")):
        if detail.startswith(prefix):
            try:
                found = uuid.UUID(detail.removeprefix(prefix))
            except ValueError:
                return None
            return PictureAim(**{field: found}) if detail == f"{prefix}{found}" else None
    return None


def is_picture_detail(detail: str) -> bool:
    return picture_aim(detail) is not None
