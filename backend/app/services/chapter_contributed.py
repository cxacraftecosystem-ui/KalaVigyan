from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Sequence
from typing import Protocol

from app.research.chapter_keys import CHAPTER_KEYS, DISCIPLINE_CHAPTERS
from app.research.craft_contributed import (
    CONTRIBUTED_PER_CHAPTER_MAX,
    ContributedPlate,
    contributed_credit,
    contributed_url,
)
from app.research.craft_parts import ContributedPart
from app.research.image_contributions import AI_GENERATED
from app.research.vocabulary import FACT_LEVELS

from .chapter_context import ChapterContext
from .chapter_draft import ChapterDraft, Drafted
from .contributed_pictures import ContributedRecord

__all__ = [
    "PlacedRecord",
    "contributed_chapter",
    "contributed_plate",
    "every_fact_listed",
    "with_contributed",
]

MADE = "made"
GLANCE = "glance"
LADDER = "process_ladder"


def with_contributed(ctx: ChapterContext, drafts: Sequence[ChapterDraft]) -> list[ChapterDraft]:
    shelves: dict[str, list[ContributedPlate]] = {}
    for record in ctx.records.contributed:
        plate = contributed_plate(ctx, record)
        if plate is None:
            continue
        shelf = shelves.setdefault(contributed_chapter(ctx, record), [])
        if len(shelf) < CONTRIBUTED_PER_CHAPTER_MAX:
            shelf.append(plate)
    if not shelves:
        return list(drafts)
    placed = [_shelved(draft, shelves.pop(draft.key, [])) for draft in drafts]
    placed += [ChapterDraft(key, None, [_item(plates)]) for key, plates in shelves.items()]
    return sorted(placed, key=lambda draft: CHAPTER_KEYS.index(draft.key))


def contributed_plate(ctx: ChapterContext, record: ContributedRecord) -> ContributedPlate | None:
    ai = record.origin == AI_GENERATED
    if ai and not every_fact_listed(ctx, record.claim_ids):
        return None
    made_with = record.generator if ai else None
    return ContributedPlate(
        contribution_id=record.contribution_id,
        url=contributed_url(record.contribution_id),
        mime=record.mime,
        width=record.width,
        height=record.height,
        origin=record.origin,
        made_with=made_with,
        caption=record.caption,
        alt_text=record.alt_text,
        credit=contributed_credit(record.origin, made_with),
        stage_id=record.stage_id,
        sentences=ctx.facts(record.claim_ids, f"contributed-{str(record.contribution_id)[:8]}"),
    )


class PlacedRecord(Protocol):
    @property
    def stage_id(self) -> uuid.UUID | None: ...

    @property
    def claim_ids(self) -> Sequence[uuid.UUID]: ...


def contributed_chapter(ctx: ChapterContext, record: PlacedRecord) -> str:
    if record.stage_id is not None:
        return MADE
    fields = [ctx.claims[claim_id].discipline for claim_id in _facts(ctx, record.claim_ids)]
    counted = Counter(DISCIPLINE_CHAPTERS[field] for field in fields if field in DISCIPLINE_CHAPTERS)
    if not counted:
        return GLANCE
    return min(counted, key=lambda key: (-counted[key], CHAPTER_KEYS.index(key)))


def every_fact_listed(ctx: ChapterContext, claim_ids: Sequence[uuid.UUID]) -> bool:
    return bool(claim_ids) and len(_facts(ctx, claim_ids)) == len(set(claim_ids))


def _facts(ctx: ChapterContext, claim_ids: Sequence[uuid.UUID]) -> list[uuid.UUID]:
    return [
        claim_id
        for claim_id in dict.fromkeys(claim_ids)
        if claim_id in ctx.claims and ctx.claims[claim_id].level in FACT_LEVELS
    ]


def _shelved(draft: ChapterDraft, plates: list[ContributedPlate]) -> ChapterDraft:
    if not plates:
        return draft
    items = list(draft.items)
    at = len(items)
    if draft.key == MADE:
        at = next((n + 1 for n, drafted in enumerate(items) if drafted.kind == LADDER), at)
    items.insert(at, _item(plates))
    return ChapterDraft(draft.key, draft.opener, items)


def _item(plates: list[ContributedPlate]) -> Drafted:
    return Drafted.of_part(ContributedPart(kind="contributed", pictures=plates))
