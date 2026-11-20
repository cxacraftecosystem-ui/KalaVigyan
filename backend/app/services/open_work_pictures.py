from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Craft, ImageContribution, Material, Process, ProcessStage, StageMaterial
from app.research.image_contributions_tasks import CRAFT_SUBJECT, PICTURE_TASK, PictureAim, picture_detail
from app.research.open_work import TASK_PROMPTS, OpenTask, SubjectStanding, task_key
from app.research.open_work_tasks import subject_priority

__all__ = ["PICTURE_ACCEPTANCE", "PICTURE_HOLDING", "craft_materials", "picture_tasks"]

PICTURE_HOLDING = ("PENDING", "APPROVED")
MASTHEAD = "MASTHEAD"
RECORD = "RECORD"
PICTURE_ACCEPTANCE = (
    "Give it with give_pictures, naming this task_key: a photograph, a drawing or an AI "
    "illustration, with its caption, its description and the declaration the person confirmed. The task closes "
    "when the picture is approved."
)


@dataclass(frozen=True)
class _Want:
    aim: PictureAim
    needed: str


@dataclass
class _Found:
    stages: dict[uuid.UUID, list[tuple[uuid.UUID, str]]]
    materials: dict[uuid.UUID, list[tuple[uuid.UUID, str]]]
    held: set[tuple[uuid.UUID, str]]


def craft_materials(craft_ids: Sequence[uuid.UUID]) -> Select[tuple[uuid.UUID, uuid.UUID, str]]:
    return (
        select(Process.craftId, Material.id, Material.name)
        .join(ProcessStage, ProcessStage.processId == Process.id)
        .join(StageMaterial, StageMaterial.stageId == ProcessStage.id)
        .join(Material, Material.id == StageMaterial.materialId)
        .where(Process.craftId.in_(craft_ids))
        .distinct()
    )


async def picture_tasks(session: AsyncSession, standings: Sequence[SubjectStanding]) -> list[OpenTask]:
    crafts = [s for s in standings if s.subject.kind == CRAFT_SUBJECT and not s.curated]
    if not crafts:
        return []
    ids = await _craft_ids(session, [standing.subject.slug for standing in crafts])
    found = await _found(session, list(ids.values()))
    tasks = []
    for standing in crafts:
        craft_id = ids.get(standing.subject.slug)
        if craft_id is None:
            continue
        for want in _wants(standing, craft_id, found):
            detail = picture_detail(want.aim)
            if detail is not None and (craft_id, detail) not in found.held:
                tasks.append(_task(standing, detail, want.needed))
    return tasks


def _wants(standing: SubjectStanding, craft_id: uuid.UUID, found: _Found) -> list[_Want]:
    name = standing.subject.name
    wants = [_Want(PictureAim(slot=MASTHEAD), f"A first picture for the page of {name}, shown at its top.")]
    if standing.gi:
        wants.append(_Want(PictureAim(slot=RECORD), f"A picture of {name} as registered, for its GI record."))
    wants += [
        _Want(PictureAim(stage_id=stage_id), f"A picture of the stage {stage} of {name}, as it is done.")
        for stage_id, stage in found.stages.get(craft_id, [])
    ]
    wants += [
        _Want(PictureAim(material_id=material_id), f"A picture of {material}, a material of {name}.")
        for material_id, material in found.materials.get(craft_id, [])
    ]
    return wants


def _task(standing: SubjectStanding, detail: str, needed: str) -> OpenTask:
    return OpenTask(
        key=task_key(PICTURE_TASK, standing.subject, detail),
        kind=PICTURE_TASK,
        priority=subject_priority(standing),
        subject=standing.subject,
        needed=needed,
        acceptance=PICTURE_ACCEPTANCE,
        count=1,
        prompt=TASK_PROMPTS.get(PICTURE_TASK),
    )


async def _craft_ids(session: AsyncSession, slugs: list[str]) -> dict[str, uuid.UUID]:
    rows = await session.execute(select(Craft.slug, Craft.id).where(Craft.slug.in_(slugs)))
    return {str(slug): craft_id for slug, craft_id in rows.all()}


async def _found(session: AsyncSession, craft_ids: list[uuid.UUID]) -> _Found:
    stages: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = defaultdict(list)
    staged = await session.execute(
        select(Process.craftId, ProcessStage.id, ProcessStage.name)
        .join(ProcessStage, ProcessStage.processId == Process.id)
        .where(Process.craftId.in_(craft_ids))
        .order_by(Process.craftId, Process.name, ProcessStage.ordinal)
    )
    for craft_id, stage_id, name in staged.all():
        stages[craft_id].append((stage_id, name))
    materials: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = defaultdict(list)
    rows = (await session.execute(craft_materials(craft_ids))).all()
    for craft_id, material_id, name in sorted(rows, key=lambda row: (str(row[0]), row[2], str(row[1]))):
        materials[craft_id].append((material_id, name))
    return _Found(stages, materials, await _held(session, craft_ids))


async def _held(session: AsyncSession, craft_ids: list[uuid.UUID]) -> set[tuple[uuid.UUID, str]]:
    rows = await session.execute(
        select(
            ImageContribution.craftId,
            ImageContribution.stageId,
            ImageContribution.materialId,
            ImageContribution.slot,
        ).where(ImageContribution.craftId.in_(craft_ids), ImageContribution.status.in_(PICTURE_HOLDING))
    )
    held = set()
    for craft_id, stage_id, material_id, slot in rows.all():
        detail = picture_detail(PictureAim(stage_id=stage_id, material_id=material_id, slot=slot))
        if detail is not None:
            held.add((craft_id, detail))
    return held
