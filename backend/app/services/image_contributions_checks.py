from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import Craft, Process, ProcessStage
from app.models.science import live_process
from app.research.image_contributions import PictureTarget
from app.research.image_contributions_tasks import CRAFT_SUBJECT, PICTURE_TASK, PictureAim, picture_aim
from app.research.open_work import parse_task_key
from app.research.retrieval import OPEN_CHUNK_ACLS

from . import knowledge_view
from .open_work_pictures import craft_materials

__all__ = [
    "aimed",
    "check_claims",
    "checked_craft",
    "checked_target",
    "material_name",
    "stage_name",
]

NO_CRAFT = "No craft has the slug {slug}"
NO_STAGE = "That stage is not one of this craft's"
NO_MATERIAL = "That material is not one of this craft's"
NO_FACT = "No shown fact has the id {claim_id}"
NOT_THIS_TASK = (
    "{key} is not a picture task of this craft and what it shows; list_open_work gives the picture tasks"
)


async def checked_craft(session: AsyncSession, slug: str) -> Craft:
    craft = await knowledge_view.resolve_craft(session, slug)
    if craft is None:
        raise InvalidInput(NO_CRAFT.format(slug=slug))
    return craft


def aimed[Aimed: PictureTarget](craft: Craft, target: Aimed) -> Aimed:
    if target.task_key is None:
        return target
    key = parse_task_key(target.task_key)
    aim = picture_aim(key.detail) if key.detail is not None else None
    if key.kind != PICTURE_TASK or key.subject_kind != CRAFT_SUBJECT or key.slug != craft.slug or aim is None:
        raise InvalidInput(NOT_THIS_TASK.format(key=target.task_key))
    given = PictureAim(stage_id=target.stage_id, material_id=target.material_id, slot=target.slot)
    if given == PictureAim():
        return target.model_copy(
            update={"stage_id": aim.stage_id, "material_id": aim.material_id, "slot": aim.slot}
        )
    if given != aim:
        raise InvalidInput(NOT_THIS_TASK.format(key=target.task_key))
    return target


async def checked_target[Aimed: PictureTarget](session: AsyncSession, craft: Craft, target: Aimed) -> Aimed:
    found = aimed(craft, target)
    if found.stage_id is not None and await stage_name(session, craft.id, found.stage_id) is None:
        raise InvalidInput(NO_STAGE)
    if found.material_id is not None and await material_name(session, craft.id, found.material_id) is None:
        raise InvalidInput(NO_MATERIAL)
    return found


async def stage_name(session: AsyncSession, craft_id: uuid.UUID, stage_id: uuid.UUID) -> str | None:
    return await session.scalar(
        select(ProcessStage.name)
        .join(Process, Process.id == ProcessStage.processId)
        .where(ProcessStage.id == stage_id, Process.craftId == craft_id, live_process())
    )


async def material_name(session: AsyncSession, craft_id: uuid.UUID, material_id: uuid.UUID) -> str | None:
    rows = await session.execute(craft_materials([craft_id]))
    return next((name for _, found, name in rows.all() if found == material_id), None)


async def check_claims(session: AsyncSession, claim_ids: Sequence[uuid.UUID]) -> None:
    if not claim_ids:
        return
    shown, _ = await knowledge_view.claims_by_id(session, claim_ids, acls=OPEN_CHUNK_ACLS)
    missing = [claim_id for claim_id in claim_ids if claim_id not in shown]
    if missing:
        raise InvalidInput(NO_FACT.format(claim_id=missing[0]))
