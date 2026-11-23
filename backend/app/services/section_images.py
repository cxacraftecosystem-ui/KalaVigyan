from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ExternalFailure
from app.research.blocks import ImageItem, ImagesBlock
from app.research.image_relevance import (
    CLAIMS_PER_IMAGE_MAX,
    SECTION_IMAGES_MAX,
    SECTION_LINK_CARDS_MAX,
    ChosenImage,
    ClaimText,
    choose_images,
    topic_words,
)
from app.research.images import ImageCandidate, ImageQuery, ImageSource
from app.research.media_refs import MediaRef

from .live_sources import LiveSourcesStore
from .media_ref_store import INLINE_DISPLAY, TEXT_RELEVANCE, SqlMediaStore, StoredPicture
from .picture_sites import blocked_picture

__all__ = [
    "CANDIDATES_PER_SOURCE",
    "IMAGE_SEARCH_SECONDS",
    "MediaStore",
    "SectionImages",
    "SectionImagesAsk",
    "image_search_text",
    "search_texts",
    "searched_images",
    "section_images",
    "shown_candidates",
    "stored_items",
]

logger = logging.getLogger(__name__)

CANDIDATES_PER_SOURCE = 10
IMAGE_SEARCH_SECONDS = 6.0
VISION_RELEVANCE = "VISION"


class MediaStore(Protocol):
    async def claim_texts(self, claim_ids: Sequence[uuid.UUID]) -> list[ClaimText]: ...

    async def stored(self, claim_ids: Sequence[uuid.UUID]) -> list[StoredPicture]: ...

    async def keep(self, chosen: Sequence[ChosenImage]) -> list[MediaRef]: ...


@dataclass(frozen=True)
class SectionImagesAsk:
    block_id: str
    craft_name: str | None
    claim_ids: tuple[uuid.UUID, ...]
    topic: str | None = None


@dataclass(frozen=True)
class SectionImages:
    sources: tuple[ImageSource, ...]
    store: MediaStore
    search_seconds: float = IMAGE_SEARCH_SECONDS

    async def block(self, ask: SectionImagesAsk) -> ImagesBlock | None:
        claims = await self.store.claim_texts(ask.claim_ids)
        if not claims:
            return None
        stored = stored_items(await self.store.stored([claim.claim_id for claim in claims]))
        if stored:
            return ImagesBlock(id=ask.block_id, kind="images", version=1, reuse=None, items=stored)
        named = ask.craft_name or ""
        texts = search_texts(ask, claims)
        found = await asyncio.gather(*(self._candidates(source, texts) for source in self.sources))
        chosen = choose_images(shown_candidates(c for batch in found for c in batch), claims, leave_out=named)
        if not chosen:
            return None
        kept = await self.store.keep(chosen)
        items = [
            ImageItem(media=media, claim_ids=list(image.illustration.claim_ids), relevance=TEXT_RELEVANCE)
            for media, image in zip(kept, chosen, strict=True)
        ]
        return ImagesBlock(id=ask.block_id, kind="images", version=1, reuse=None, items=items)

    async def _candidates(self, source: ImageSource, texts: Sequence[str]) -> list[ImageCandidate]:
        return await searched_images(source, texts, seconds=self.search_seconds)


async def searched_images(
    source: ImageSource, texts: Sequence[str], *, seconds: float
) -> list[ImageCandidate]:
    try:
        async with asyncio.timeout(seconds):
            return await _searched(source, texts)
    except ExternalFailure as failure:
        logger.warning("%s image search failed (%s)", source.name, failure.kind)
    except TimeoutError:
        logger.warning("%s image search took over %s s; its pictures are left out", source.name, seconds)
    return []


async def _searched(source: ImageSource, texts: Sequence[str]) -> list[ImageCandidate]:
    for text in dict.fromkeys(t for t in texts if len(t) >= 2):
        found = await source.images(ImageQuery(text=text), CANDIDATES_PER_SOURCE)
        if found:
            return found
    return []


def shown_candidates(candidates: Iterable[ImageCandidate]) -> list[ImageCandidate]:
    kept = []
    for candidate in candidates:
        if blocked_picture(page_url=candidate.page_url, image_url=candidate.image_url, title=candidate.title):
            logger.info("a picture from %s is left out: shops and social sites are not shown", candidate.site)
            continue
        kept.append(candidate)
    return kept


def stored_items(pictures: Iterable[StoredPicture]) -> list[ImageItem]:
    linked: dict[uuid.UUID, list[StoredPicture]] = {}
    for picture in pictures:
        media = picture.media
        if blocked_picture(page_url=media.page_url, image_url=media.image_url, title=media.title):
            continue
        linked.setdefault(media.id, []).append(picture)
    ordered = sorted(linked.values(), key=lambda links: links[0].media.display != INLINE_DISPLAY)
    items: list[ImageItem] = []
    cards = 0
    for links in ordered:
        card = links[0].media.display != INLINE_DISPLAY
        if card and cards >= SECTION_LINK_CARDS_MAX:
            continue
        cards += card
        items.append(_stored_item(links))
    return items[:SECTION_IMAGES_MAX]


def _stored_item(links: Sequence[StoredPicture]) -> ImageItem:
    shown = list(dict.fromkeys(link.claim_id for link in links))[:CLAIMS_PER_IMAGE_MAX]
    seen = all(link.relevance == VISION_RELEVANCE for link in links if link.claim_id in shown)
    return ImageItem(
        media=links[0].media, claim_ids=shown, relevance=VISION_RELEVANCE if seen else TEXT_RELEVANCE
    )


def search_texts(ask: SectionImagesAsk, claims: Sequence[ClaimText]) -> tuple[str, ...]:
    named = ask.craft_name or ""
    if ask.topic:
        return (f"{named} {ask.topic}".strip(), ask.topic, named)
    return (image_search_text(named, claims), named)


def image_search_text(craft_name: str, claims: Sequence[ClaimText]) -> str:
    words = topic_words(claims, leave_out=craft_name)
    return " ".join(part for part in (craft_name, *words) if part).strip()


async def section_images(sessions: async_sessionmaker[AsyncSession], live: LiveSourcesStore) -> SectionImages:
    return SectionImages(sources=await live.web_images(sessions), store=SqlMediaStore(sessions))
