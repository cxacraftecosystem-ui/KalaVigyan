from __future__ import annotations

import logging
from collections.abc import Sequence

from app.core.errors import ExternalFailure
from app.research.images import ImageCandidate, ImageQuery, ImageSource

from ..adapter import checked_k

__all__ = ["WEB_IMAGES_FALLBACK_MIN_CARDS", "WebImages", "with_web_image_fallback"]

WEB_IMAGES_FALLBACK_MIN_CARDS = 2

logger = logging.getLogger(__name__)


class WebImages:
    def __init__(self, primary: ImageSource, fallback: ImageSource) -> None:
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name

    async def images(self, query: ImageQuery, k: int) -> list[ImageCandidate]:
        wanted = checked_k(k)
        cards, failure = await self._primary_cards(query, wanted)
        if len(cards) >= min(WEB_IMAGES_FALLBACK_MIN_CARDS, wanted):
            return cards
        try:
            extra = await self.fallback.images(query, wanted)
        except ExternalFailure as fallback_failure:
            if failure is not None:
                raise fallback_failure from failure
            logger.warning("%s image fallback failed (%s)", self.fallback.name, fallback_failure.kind)
            return cards
        seen = {card.original_key for card in cards}
        return [*cards, *(card for card in extra if card.original_key not in seen)][:wanted]

    async def _primary_cards(
        self, query: ImageQuery, k: int
    ) -> tuple[list[ImageCandidate], ExternalFailure | None]:
        try:
            return await self.primary.images(query, k), None
        except ExternalFailure as failure:
            logger.warning(
                "%s image search failed (%s); asking %s", self.primary.name, failure.kind, self.fallback.name
            )
            return [], failure


def with_web_image_fallback(
    sources: Sequence[ImageSource], *, primary_name: str, fallback: ImageSource | None
) -> tuple[ImageSource, ...]:
    if fallback is None:
        return tuple(sources)
    return tuple(WebImages(source, fallback) if source.name == primary_name else source for source in sources)
