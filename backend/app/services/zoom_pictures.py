from __future__ import annotations

import asyncio
import dataclasses
import re
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.research.blocks import named_in_texts
from app.research.blocks_journey import IMAGE_ZOOM_LEVELS
from app.research.image_relevance import (
    CLAIMS_PER_IMAGE_MAX,
    ChosenImage,
    ClaimText,
    Illustration,
    illustration,
)
from app.research.images import ImageCandidate, ImageSource, shown_inline
from app.research.media_refs import MediaRef
from app.research.quotes import content_stems

from .live_sources import LiveSourcesStore
from .media_ref_store import INLINE_DISPLAY, TEXT_RELEVANCE, SqlMediaStore, StoredPicture
from .section_images import IMAGE_SEARCH_SECONDS, image_search_text, searched_images
from .term_scales import scale_stripped

__all__ = [
    "FIBRE_NAMES",
    "LEVEL_WORDS",
    "ZOOM_IMAGE_SOURCES",
    "LevelPicture",
    "LevelTerm",
    "PictureKeeper",
    "PicturesAsk",
    "ZoomPictures",
    "fibre_named",
    "fibre_tagged",
    "picture_level",
    "zoom_pictures",
]

ZOOM_IMAGE_SOURCES = frozenset({"wikimedia_commons", "openverse"})
FIBRE_NAMES = (
    "cotton",
    "silk",
    "wool",
    "jute",
    "linen",
    "flax",
    "hemp",
    "ramie",
    "sisal",
    "coir",
    "pashmina",
    "cashmere",
)
LEVEL_WORDS = MappingProxyType(
    {
        "FIBRE": frozenset(
            {"micrograph", "micrographs", "microscope", "microscopic", "microscopy", "magnified", "sem"}
        ),
        "WORKSHOP": frozenset(
            {
                "workshop",
                "workshops",
                "artisan",
                "artisans",
                "craftsman",
                "craftsmen",
                "craftswoman",
                "craftswomen",
                "printer",
                "printers",
                "printing",
                "weaver",
                "weavers",
                "weaving",
                "dyer",
                "dyers",
                "dyeing",
                "potter",
                "potters",
                "loom",
                "looms",
                "kiln",
                "kilns",
                "studio",
                "karkhana",
                "carver",
                "carvers",
                "embroiderer",
                "embroiderers",
            }
        ),
        "CLOTH": frozenset(
            {
                "cloth",
                "cloths",
                "fabric",
                "fabrics",
                "textile",
                "textiles",
                "sari",
                "saris",
                "saree",
                "sarees",
                "shawl",
                "shawls",
                "dupatta",
                "dupattas",
                "stole",
                "stoles",
                "garment",
                "garments",
                "turban",
                "turbans",
                "bedspread",
                "bedspreads",
                "scarf",
                "scarves",
            }
        ),
    }
)
LEVEL_CHECK_ORDER = ("FIBRE", "WORKSHOP", "CLOTH")
FIBRE_LEVEL = "FIBRE"
WORD = re.compile(r"[^\W\d_]+")


class PictureKeeper(Protocol):
    async def keep(self, chosen: Sequence[ChosenImage]) -> list[MediaRef]: ...


@dataclass(frozen=True)
class LevelPicture:
    level: str
    media: MediaRef
    relevance: str
    claim_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class LevelTerm:
    level: str
    label: str
    surfaces: tuple[str, ...]

    def named_in(self, text: str) -> bool:
        return any(named_in_texts(surface, (text,)) for surface in self.surfaces)


@dataclass(frozen=True)
class PicturesAsk:
    craft_name: str
    claims: tuple[ClaimText, ...]
    fibre: str | None
    stored: tuple[StoredPicture, ...]
    terms: tuple[LevelTerm, ...] = ()


@dataclass(frozen=True)
class ZoomPictures:
    sources: tuple[ImageSource, ...]
    keeper: PictureKeeper
    search_seconds: float = IMAGE_SEARCH_SECONDS
    figures: ImageSource | None = None

    async def pictures(self, asked: PicturesAsk) -> dict[str, LevelPicture]:
        ask = dataclasses.replace(asked, fibre=asked.fibre or fibre_tagged(asked.terms))
        found = stored_level_pictures(ask)
        wanted = [level for level in IMAGE_ZOOM_LEVELS if level not in found and _searchable(level, ask)]
        if not wanted or not ask.claims:
            return found
        candidates = await self._candidates(_search_texts(ask, wanted))
        chosen = chosen_level_images(candidates, ask, wanted)
        if FIBRE_LEVEL in wanted and FIBRE_LEVEL not in chosen:
            chosen |= await self._figure(ask)
        if not chosen:
            return found
        kept = await self.keeper.keep(list(chosen.values()))
        for (level, image), media in zip(chosen.items(), kept, strict=True):
            if media.display == INLINE_DISPLAY:
                found[level] = LevelPicture(level, media, TEXT_RELEVANCE, image.illustration.claim_ids)
        return found

    async def _candidates(self, searches: Sequence[tuple[str, ...]]) -> list[ImageCandidate]:
        found = await asyncio.gather(
            *(
                searched_images(source, texts, seconds=self.search_seconds)
                for texts in searches
                for source in self.sources
            )
        )
        return [candidate for batch in found for candidate in batch]

    async def _figure(self, ask: PicturesAsk) -> dict[str, ChosenImage]:
        if self.figures is None or ask.fibre is None:
            return {}
        found = await searched_images(self.figures, _fibre_texts(ask.fibre), seconds=self.search_seconds)
        return chosen_level_images(found, ask, [FIBRE_LEVEL])


def picture_level(text: str, fibre: str | None, terms: Sequence[LevelTerm] = ()) -> str | None:
    words = set(WORD.findall(text.casefold()))
    tagged = {term.level for term in terms if term.named_in(text)}
    for level in LEVEL_CHECK_ORDER:
        if level == FIBRE_LEVEL:
            if words & LEVEL_WORDS[level] and fibre is not None and named_in_texts(fibre, (text,)):
                return level
        elif words & LEVEL_WORDS[level] or level in tagged:
            return level
    return None


def fibre_tagged(terms: Iterable[LevelTerm]) -> str | None:
    tagged = next((term for term in terms if term.level == FIBRE_LEVEL), None)
    return None if tagged is None else scale_stripped(tagged.label, FIBRE_LEVEL)


def fibre_named(names: Iterable[str]) -> str | None:
    for name in names:
        words = set(WORD.findall(name.casefold()))
        found = next((fibre for fibre in FIBRE_NAMES if fibre in words), None)
        if found is not None:
            return found
    return None


def stored_level_pictures(ask: PicturesAsk) -> dict[str, LevelPicture]:
    found: dict[str, LevelPicture] = {}
    for picture in ask.stored:
        level = picture_level(f"{picture.media.title}\n{picture.media.alt}", ask.fibre, ask.terms)
        if level is not None and level not in found:
            found[level] = LevelPicture(level, picture.media, picture.relevance, (picture.claim_id,))
    return found


def chosen_level_images(
    candidates: Sequence[ImageCandidate], ask: PicturesAsk, wanted: Sequence[str]
) -> dict[str, ChosenImage]:
    ranked: dict[str, list[tuple[int, int, ChosenImage]]] = {}
    for position, candidate in enumerate(candidates):
        level = picture_level(candidate.described, ask.fibre, ask.terms) if shown_inline(candidate) else None
        shown = _illustrated(candidate, ask, level) if level in wanted else None
        if level is not None and shown is not None:
            ranked.setdefault(level, []).append((-shown.shared, position, ChosenImage(candidate, shown)))
    chosen: dict[str, ChosenImage] = {}
    taken: set[str] = set()
    for level in wanted:
        for _, _, image in sorted(ranked.get(level, []), key=lambda entry: entry[:2]):
            if image.candidate.original_key not in taken:
                chosen[level] = image
                taken.add(image.candidate.original_key)
                break
    return chosen


async def zoom_pictures(sessions: async_sessionmaker[AsyncSession], live: LiveSourcesStore) -> ZoomPictures:
    sources = tuple(source for source in await live.images() if source.name in ZOOM_IMAGE_SOURCES)
    return ZoomPictures(sources=sources, keeper=SqlMediaStore(sessions), figures=await live.figures())


def _illustrated(candidate: ImageCandidate, ask: PicturesAsk, level: str) -> Illustration | None:
    if level != "FIBRE":
        return illustration(candidate, ask.claims, leave_out=ask.craft_name)
    fibre = ask.fibre or ""
    naming = [claim.claim_id for claim in ask.claims if content_stems(fibre) <= content_stems(claim.text)]
    if not naming:
        return None
    return Illustration(claim_ids=tuple(naming[:CLAIMS_PER_IMAGE_MAX]), shared=len(content_stems(fibre)))


def _searchable(level: str, ask: PicturesAsk) -> bool:
    return level != "FIBRE" or ask.fibre is not None


def _search_texts(ask: PicturesAsk, wanted: Sequence[str]) -> list[tuple[str, ...]]:
    searches: list[tuple[str, ...]] = []
    if any(level != "FIBRE" for level in wanted):
        searches.append((image_search_text(ask.craft_name, ask.claims), ask.craft_name))
    if "FIBRE" in wanted and ask.fibre is not None:
        searches.append(_fibre_texts(ask.fibre))
    return searches


def _fibre_texts(fibre: str) -> tuple[str, ...]:
    return (f"{fibre} fibre micrograph", f"{fibre} fiber micrograph")
