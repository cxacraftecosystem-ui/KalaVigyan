from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from app.core.errors import ExternalFailure, InvalidInput
from app.planner.policy import SEARCH_TIMEOUT_SECONDS
from app.research.images import ImageCandidate, ImageQuery, ImageSource, openly_licensed
from app.sources.reference.commons_urls import commons_thumbnail_url

from .source_lookup_models import FoundPicture, FoundPictures, PictureWidth

__all__ = ["COMMONS_WIDTHS", "PICTURES_MAX", "PICTURES_PER_SOURCE", "found_pictures", "picture_widths"]

logger = logging.getLogger(__name__)

COMMONS_WIDTHS = (330, 500, 960, 1280, 1920)
PICTURES_PER_SOURCE = 12
PICTURES_MAX = 24
EVERY_SEARCH_FAILED = "Every picture search failed just now; nothing was found. Try again in a few minutes."


async def found_pictures(sources: Sequence[ImageSource], query: str) -> FoundPictures:
    asked = ImageQuery(text=query)
    results = await asyncio.gather(*(_searched(source, asked) for source in sources))
    answered = [source.name for source, found in zip(sources, results, strict=True) if found is not None]
    if sources and not answered:
        raise InvalidInput(EVERY_SEARCH_FAILED)
    seen: set[str] = set()
    pictures: list[FoundPicture] = []
    for candidate in (candidate for found in results if found for candidate in found):
        if candidate.original_key in seen or not openly_licensed(candidate) or not candidate.author:
            continue
        seen.add(candidate.original_key)
        pictures.append(_picture(candidate, candidate.author))
    return FoundPictures(
        query=query,
        pictures=pictures[:PICTURES_MAX],
        searched=answered,
        unavailable=[source.name for source in sources if source.name not in answered],
    )


def picture_widths(original_url: str, width: int | None) -> list[PictureWidth]:
    fitting = [step for step in COMMONS_WIDTHS if width is None or step <= width]
    shown = [(step, commons_thumbnail_url(original_url, step)) for step in fitting]
    return [PictureWidth(width=step, url=url) for step, url in shown if url is not None]


async def _searched(source: ImageSource, query: ImageQuery) -> list[ImageCandidate] | None:
    try:
        return await asyncio.wait_for(source.images(query, PICTURES_PER_SOURCE), SEARCH_TIMEOUT_SECONDS)
    except (ExternalFailure, InvalidInput, TimeoutError) as failure:
        logger.warning("picture lookup: %s search failed (%s)", source.name, type(failure).__name__)
        return None


def _picture(candidate: ImageCandidate, author: str) -> FoundPicture:
    licence = candidate.licence or candidate.licence_url
    return FoundPicture(
        provider=candidate.provider,
        page_url=candidate.page_url,
        image_url=candidate.image_url,
        original_url=candidate.original_url,
        width=candidate.width,
        height=candidate.height,
        title=candidate.title,
        description=candidate.description,
        author=author,
        site=candidate.site,
        licence=candidate.licence,
        licence_url=candidate.licence_url,
        open_licence=openly_licensed(candidate),
        credit=f"Photo: {author}, {licence}, via {candidate.site}",
        widths=picture_widths(candidate.original_url, candidate.width),
    )
