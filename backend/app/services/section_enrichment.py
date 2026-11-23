from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Self

from app.research.blocks import BlockBase, ImagesBlock
from app.research.crafts import CraftRef
from app.research.explainer import Block, with_payload_sentences
from app.research.sections import block_id
from app.research.term_marking import GlossaryEntry, TermMarker

from .explainer_events import ExplainerStream
from .section_images import SectionImagesAsk

__all__ = [
    "PICTURES_WAIT_SECONDS",
    "Enrichment",
    "EnrichmentTools",
    "GlossaryOf",
    "PictureSearches",
    "PicturesOf",
    "no_pictures",
    "without_pictures",
]

logger = logging.getLogger(__name__)

PICTURES_WAIT_SECONDS = 8.0

GlossaryOf = Callable[[CraftRef], Awaitable[Sequence[GlossaryEntry]]]
PicturesOf = Callable[[SectionImagesAsk], Awaitable[ImagesBlock | None]]


@dataclass(frozen=True)
class EnrichmentTools:
    glossary: GlossaryOf
    pictures: PicturesOf
    wait_seconds: float = PICTURES_WAIT_SECONDS

    async def for_answer(self, craft: CraftRef | None) -> Enrichment:
        entries = await self._entries(craft) if craft is not None else ()
        return Enrichment(
            marker=TermMarker(entries),
            tools=self,
            craft_name=craft.name if craft is not None else None,
            term_names={entry.key: entry.surfaces for entry in entries},
        )

    async def _entries(self, craft: CraftRef) -> Sequence[GlossaryEntry]:
        try:
            return await self.glossary(craft)
        except Exception:
            logger.warning(
                "the glossary of %s was not read; sentences carry no terms", craft.slug, exc_info=True
            )
            return ()


async def no_pictures(ask: SectionImagesAsk) -> ImagesBlock | None:
    return None


def without_pictures(tools: EnrichmentTools) -> EnrichmentTools:
    return replace(tools, pictures=no_pictures)


@dataclass(frozen=True)
class Enrichment:
    marker: TermMarker
    tools: EnrichmentTools
    craft_name: str | None
    term_names: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def marked[Marked: BlockBase](self, block: Marked) -> Marked:
        payload = block.model_dump(mode="json", by_alias=True, exclude_unset=True)
        return type(block).model_validate(with_payload_sentences(payload, self._marked_sentence))

    def pictures_ask(self, section_id: str, blocks: Sequence[Block]) -> SectionImagesAsk | None:
        cited = dict.fromkeys(citation.claim_id for block in blocks for citation in block.citations())
        if not cited:
            return None
        return SectionImagesAsk(
            block_id=block_id(section_id, len(blocks) + 1),
            craft_name=self.craft_name,
            claim_ids=tuple(uuid.UUID(claim_id) for claim_id in cited),
        )

    async def pictures(self, ask: SectionImagesAsk) -> ImagesBlock | None:
        try:
            async with asyncio.timeout(self.tools.wait_seconds):
                return await self.tools.pictures(ask)
        except TimeoutError:
            logger.warning(
                "pictures for %s took over %s s; none are shown", ask.block_id, self.tools.wait_seconds
            )
        except Exception:
            logger.warning("pictures for %s failed; none are shown", ask.block_id, exc_info=True)
        return None

    def searching(self) -> PictureSearches:
        return PictureSearches(self)

    def _marked_sentence(self, sentence: Mapping[str, Any]) -> dict[str, Any]:
        spans = self.marker.spans(sentence["text"])
        return {**sentence, "terms": [span.model_dump(mode="json", by_alias=True) for span in spans]}


class PictureSearches:
    def __init__(self, enrichment: Enrichment) -> None:
        self._enrichment = enrichment
        self._running: dict[str, asyncio.Task[ImagesBlock | None]] = {}

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        running, self._running = list(self._running.values()), {}
        for task in running:
            task.cancel()
        await asyncio.gather(*running, return_exceptions=True)

    def start(self, section_id: str, blocks: Sequence[Block]) -> None:
        ask = self._enrichment.pictures_ask(section_id, blocks)
        if ask is not None and section_id not in self._running:
            self._running[section_id] = asyncio.create_task(self._enrichment.pictures(ask))

    async def sent(
        self, section_id: str, stream: ExplainerStream, *, ordinal: int | None = None
    ) -> ImagesBlock | None:
        task = self._running.pop(section_id, None)
        block = await task if task is not None else None
        if block is None:
            return None
        if ordinal is not None:
            block = block.model_copy(update={"id": block_id(section_id, ordinal)})
        shown = await stream.blocks(section_id, [block], {})
        return shown[0] if shown else None
