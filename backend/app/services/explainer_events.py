from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from typing import Any

from app.data.craft_text import fold
from app.research.blocks_lede import LedeBlock
from app.research.explainer import Block, ExplainerSection
from app.research.sections import SectionSpec
from app.research.stream import Emit, StatusStep

from .answer_events import OPEN_HEADING, OPEN_SECTION_ID
from .answer_steps import StepLog
from .answer_trail import TrailLog
from .claim_ledger import ClaimLedger
from .gap_routing import gap_block, open_question, routed_gaps
from .interface_words import InterfaceWords, reviewed_words
from .ledger_payloads import Payload
from .status_lines import status_message

__all__ = ["ONCE_STEPS", "ExplainerStream", "InLanguage", "shown_title"]

logger = logging.getLogger(__name__)

ONCE_STEPS = frozenset(
    {"SEARCHING_STORED", "RESEARCHING", "READING", "COMPOSING", "WRITING_BACK", "TRANSLATING"}
)

InLanguage = Callable[[Block], Awaitable[Block]]


def shown_title(spec: SectionSpec, titles: Mapping[str, str]) -> dict[str, str]:
    title = titles.get(spec.id, spec.title)
    return {"title": title, "original": spec.title} if title != spec.title else {"title": title}


class ExplainerStream:
    def __init__(self, emit: Emit, *, language: str, words: InterfaceWords | None = None) -> None:
        self.steps = StepLog()
        self.emit = self.steps.traced(emit)
        self.trail = TrailLog(self.emit)
        self.language = language
        self.words = reviewed_words(language) if words is None else words
        self.ledger = ClaimLedger()
        self._lock = asyncio.Lock()
        self._sent_sources: set[str] = set()
        self._section_titles: dict[str, str] = {}
        self._headings: dict[str, str] = {}
        self._totals: dict[str, int] = {}
        self._latest: tuple[str, str] = ("", "")
        self._open_questions = 0
        self._lede_settled = asyncio.Event()
        self._lede_settled.set()

    def hold_blocks_for_lede(self) -> None:
        self._lede_settled.clear()

    def release_blocks(self) -> None:
        self._lede_settled.set()

    async def lede(self, block: LedeBlock, sources: Mapping[str, Mapping[str, Any]]) -> None:
        async with self._lock:
            shown = self.ledger.admit_lede(block, sources)
            await self._sources(shown.cited_source_ids(), {**sources, **self.ledger.sources.refs()})
            await self.emit("lede", {"block": shown})

    def claim_heading(self, section_id: str, heading: str) -> bool:
        return self._headings.setdefault(fold(heading), section_id) == section_id

    def shown_before(self, sections: Iterable[ExplainerSection]) -> None:
        for section in sections:
            self.claim_heading(section.id, section.original or section.title)
            self.ledger.note_shown(section.blocks)

    async def section_heading(self, section_id: str, *, title: str, original: str | None) -> None:
        shown = {"title": title, **({"original": original} if original else {})}
        await self.emit("section_heading", {"sectionId": section_id, **shown})

    async def status(self, step: StatusStep, count: int = 0, *, craft: str = "") -> None:
        if step in ONCE_STEPS:
            shown = step in self._totals
            self._totals[step] = self._totals.get(step, 0) + count
            if shown and step != self._latest[0]:
                return
            count = self._totals[step]
        message = status_message(step, count, craft, language=self.language, words=self.words)
        if (step, message) == self._latest:
            return
        self._latest = (step, message)
        await self.emit("status", {"step": step, "message": message})

    async def section_started(self, spec: SectionSpec, *, titles: Mapping[str, str], state: str) -> None:
        shown = shown_title(spec, titles)
        self._section_titles[spec.id] = shown["title"]
        await self.emit(
            "section_started",
            {
                "id": spec.id,
                "discipline": spec.discipline,
                **shown,
                "order": spec.order,
                "state": state,
            },
        )

    async def section_state(self, section_id: str, state: str) -> None:
        await self.emit("section_state", {"sectionId": section_id, "state": state})

    async def section_done(self, section_id: str, *, searched: str | None) -> None:
        state = "EMPTY" if searched is not None else "READY"
        await self.emit("section_done", {"sectionId": section_id, "state": state, "searched": searched})

    async def blocks(
        self,
        section_id: str,
        blocks: Sequence[Block],
        sources: Mapping[str, Mapping[str, Any]],
        *,
        in_language: InLanguage | None = None,
    ) -> list[Block]:
        await self._lede_settled.wait()
        routed = routed_gaps(blocks)
        async with self._lock:
            admitted = self.ledger.admit(section_id, routed.blocks, sources)
        shown = list(await asyncio.gather(*map(in_language, admitted))) if in_language else admitted
        async with self._lock:
            known = {**sources, **self.ledger.sources.refs()}
            sent = [block for block in shown if _sourced(section_id, block, known)]
            for block in sent:
                await self._sources(block.cited_source_ids(), known)
                await self._found_piece(section_id, block)
                await self.emit("block", {"sectionId": section_id, "block": block})
        if routed.gaps:
            await self.open_questions(await _asked(section_id, routed.gaps, in_language), sources)
        return sent

    async def _found_piece(self, section_id: str, block: Block) -> None:
        marker = block.reuse
        if marker is None:
            return
        title = self._section_titles.get(section_id)
        if title is None:
            logger.warning("block %s reuses piece %s in a section never started", block.id, marker.piece_id)
            return
        await self.trail.found_piece(marker.piece_id, title=title, stored_at=marker.stored_at)

    def shown_sources(self) -> dict[str, dict[str, Any]]:
        return self.ledger.sources.refs()

    async def open_questions(
        self, sentences: Sequence[Mapping[str, Any]], sources: Mapping[str, Mapping[str, Any]]
    ) -> None:
        async with self._lock:
            for sentence in sentences:
                merged = self.ledger.merged_sentence(sentence, sources)
                known = {**sources, **self.ledger.sources.refs()}
                if not _asks_from_known(merged, known):
                    continue
                await self._sources(dict.fromkeys(c["sourceId"] for c in merged["citations"]), known)
                self._open_questions += 1
                numbered = {**merged, "id": f"{OPEN_SECTION_ID}.{self._open_questions}"}
                await self.emit(
                    "open_question",
                    {"sectionId": OPEN_SECTION_ID, "heading": OPEN_HEADING, "sentence": numbered},
                )

    async def _sources(self, source_ids: Iterable[str], sources: Mapping[str, Mapping[str, Any]]) -> None:
        for source_id in source_ids:
            if source_id not in self._sent_sources:
                self._sent_sources.add(source_id)
                await self.emit("source", sources[source_id])


async def _asked(section_id: str, gaps: Sequence[Payload], in_language: InLanguage | None) -> list[Payload]:
    plain = [open_question(gap) for gap in gaps]
    block = gap_block(section_id, gaps) if in_language is not None else None
    if in_language is None or block is None:
        return plain
    shown = await in_language(block)
    return [
        open_question(sentence.model_dump(mode="json", by_alias=True)) for sentence in shown.cited_sentences()
    ]


def _asks_from_known(sentence: Mapping[str, Any], known: Mapping[str, Mapping[str, Any]]) -> bool:
    missing = [c["sourceId"] for c in sentence.get("citations", []) if c["sourceId"] not in known]
    if missing:
        logger.warning(
            "an open question is left out: it cites sources not sent with it (%s)", ", ".join(missing)
        )
    return not missing


def _sourced(section_id: str, block: Block, known: Mapping[str, Mapping[str, Any]]) -> bool:
    missing = [source_id for source_id in block.cited_source_ids() if source_id not in known]
    if missing:
        logger.warning(
            "block %s of section %s is left out: it cites sources not sent with it (%s)",
            block.id,
            section_id,
            ", ".join(missing),
        )
    return not missing
