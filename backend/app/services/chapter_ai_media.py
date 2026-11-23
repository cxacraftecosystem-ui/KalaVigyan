from __future__ import annotations

from collections.abc import Sequence

from app.core.clock import INDIA_TZ
from app.research.chapter_keys import CHAPTER_KEYS
from app.research.craft_origins import AI_GENERATED, ItemOrigin, PageAiMedia
from app.research.craft_parts import AiMediaPart

from .chapter_context import ChapterContext
from .chapter_contributed import contributed_chapter, every_fact_listed
from .chapter_draft import ChapterDraft, Drafted
from .craft_ai_media import AiMediaRecord

__all__ = ["AI_MEDIA_PER_CHAPTER_MAX", "ai_media_item", "with_ai_media"]

MADE = "made"
LADDER = "process_ladder"
READERS = "READERS"
AI_MEDIA_PER_CHAPTER_MAX = 3


def with_ai_media(ctx: ChapterContext, drafts: Sequence[ChapterDraft]) -> list[ChapterDraft]:
    shelves = _shelves(ctx)
    if not shelves:
        return list(drafts)
    placed = [_shelved(draft, shelves.pop(draft.key, [])) for draft in drafts]
    placed += [ChapterDraft(key, None, [_item(media)]) for key, media in shelves.items()]
    return sorted(placed, key=lambda draft: CHAPTER_KEYS.index(draft.key))


def ai_media_item(ctx: ChapterContext, record: AiMediaRecord) -> PageAiMedia | None:
    if record.kind not in AI_GENERATED or not every_fact_listed(ctx, record.claim_ids):
        return None
    sentences = ctx.facts(record.claim_ids, f"ai-media-{str(record.asset_id)[:8]}")
    if not sentences or not record.alt_text or not record.model:
        return None
    origin = ItemOrigin(
        basis=READERS,
        generated=AI_GENERATED[record.kind],
        model=record.model,
        generated_on=record.made_at.astimezone(INDIA_TZ).date().isoformat(),
    )
    return PageAiMedia(
        asset_id=record.asset_id,
        kind=record.kind,
        url=f"/api/crafts/media/{record.asset_id}",
        mime=record.mime,
        width=record.width,
        height=record.height,
        duration_seconds=record.duration_seconds,
        alt_text=record.alt_text,
        sentences=sentences,
        stage_id=record.stage_id,
        origin=origin,
    )


def _shelves(ctx: ChapterContext) -> dict[str, list[PageAiMedia]]:
    shelves: dict[str, list[PageAiMedia]] = {}
    staged: set[tuple[object, str]] = set()
    for record in ctx.records.ai_media:
        media = ai_media_item(ctx, record)
        if media is None:
            continue
        shelf = shelves.setdefault(contributed_chapter(ctx, record), [])
        if record.stage_id is not None:
            if (record.stage_id, record.kind) in staged:
                continue
            staged.add((record.stage_id, record.kind))
        elif len(shelf) >= AI_MEDIA_PER_CHAPTER_MAX:
            continue
        shelf.append(media)
    return {key: shelf for key, shelf in shelves.items() if shelf}


def _shelved(draft: ChapterDraft, media: list[PageAiMedia]) -> ChapterDraft:
    if not media:
        return draft
    items = list(draft.items)
    at = len(items)
    if draft.key == MADE:
        at = next((n + 1 for n, drafted in enumerate(items) if drafted.kind == LADDER), at)
    items.insert(at, _item(media))
    return ChapterDraft(draft.key, draft.opener, items)


def _item(media: list[PageAiMedia]) -> Drafted:
    return Drafted.of_part(AiMediaPart(kind="ai_media", media=media))
