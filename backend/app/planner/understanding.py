from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from app.core.errors import AppError, ExternalFailure, spend_refusal
from app.research.coverage_seats import covering_seats, relevant_fields
from app.research.crafts import COMPARED_CRAFTS_MAX, MAX_CANDIDATES, CraftQuery, CraftRef, CraftResolution
from app.research.depth import depth_policy, effective_depth
from app.research.expert_panel import WIDENED_DEPTHS
from app.research.sections import answer_fields, question_fields
from app.research.structured import StructuredModel
from app.research.understanding import UnderstandAsk, Understanding, UnknownCraft

from .understanding_prompt import (
    UNDERSTAND_SYSTEM_PROMPT,
    UnderstandReply,
    parsed_reply,
    understand_message,
    understand_schema,
)

__all__ = [
    "CraftChoice",
    "HeldFields",
    "ModelUnderstander",
    "Reading",
    "Resolve",
    "asked_fields",
    "chosen_craft",
    "compared_choice",
    "understood_seats",
]

logger = logging.getLogger(__name__)

Resolve = Callable[[CraftQuery], Awaitable[CraftResolution]]
HeldFields = Callable[[str], Awaitable[Sequence[str]]]


@dataclass(frozen=True)
class Reading:
    reply: UnderstandReply | None
    degraded: bool = False
    refusal: str | None = None


@dataclass(frozen=True)
class CraftChoice:
    craft: CraftRef | None
    others: tuple[CraftRef, ...] = ()
    compared: tuple[CraftRef, ...] = ()


class ModelUnderstander:
    def __init__(self, *, model: StructuredModel, resolve: Resolve, held: HeldFields | None = None) -> None:
        self._model = model
        self._resolve = resolve
        self._held = held

    async def understand(self, ask: UnderstandAsk) -> Understanding:
        resolution = await self._resolution(ask)
        if ask.craft_slug is not None and (resolution is None or resolution.status != "RESOLVED"):
            raise UnknownCraft(ask.craft_slug)
        offered = _offered(resolution)
        reading = await self._read(ask, offered)
        choice = chosen_craft(ask, resolution, reading.reply)
        if choice.craft is None and not ask.any_craft and reading.reply is not None:
            choice = await self._named(reading.reply, offered)
        chosen = compared_choice(ask, choice, reading.reply, offered)
        return _understanding(ask, chosen, reading, await self._held_fields(chosen.craft, reading))

    async def _held_fields(self, craft: CraftRef | None, reading: Reading) -> tuple[str, ...] | None:
        if self._held is None or craft is None or reading.refusal is not None:
            return None
        try:
            return tuple(await self._held(craft.slug))
        except AppError as error:
            logger.warning(
                "the fields %s holds were not read, so seats follow the question: %s", craft.slug, error
            )
            return None

    async def _resolution(self, ask: UnderstandAsk) -> CraftResolution | None:
        query = CraftQuery(text=ask.question, craft_slug=ask.craft_slug, language=ask.language)
        try:
            return await self._resolve(query)
        except AppError as error:
            if ask.craft_slug is not None or spend_refusal(error):
                raise
            logger.warning("finding the craft failed, so the question is understood without it: %s", error)
            return None

    async def _read(self, ask: UnderstandAsk, offered: Sequence[CraftRef]) -> Reading:
        try:
            reply = await self._model(
                system=UNDERSTAND_SYSTEM_PROMPT,
                user=understand_message(ask, offered),
                schema=understand_schema(offered),
            )
        except AppError as error:
            logger.warning("understanding the question fell back to the craft resolver: %s", error)
            return Reading(reply=None, refusal=spend_refusal(error))
        try:
            return Reading(reply=parsed_reply(reply, offered), degraded=reply.degraded)
        except ExternalFailure as error:
            logger.warning("understanding the question fell back to the craft resolver: %s", error)
            return Reading(reply=None, degraded=reply.degraded)

    async def _named(self, reply: UnderstandReply, offered: Sequence[CraftRef]) -> CraftChoice:
        chosen: CraftRef | None = None
        others: list[CraftRef] = list(offered)
        listed = {craft.name.casefold() for craft in offered}
        for name in (name for name in reply.craft_names if name.casefold() not in listed):
            try:
                resolution = await self._resolve(CraftQuery(text=name))
            except AppError as error:
                logger.warning("a craft the question names could not be looked up: %s", error)
                continue
            if chosen is None and resolution.status == "RESOLVED":
                chosen = resolution.craft
            others.extend(candidate.craft for candidate in resolution.candidates)
        return CraftChoice(craft=chosen, others=_distinct(others, without=chosen))


def chosen_craft(
    ask: UnderstandAsk, resolution: CraftResolution | None, reply: UnderstandReply | None
) -> CraftChoice:
    offered = _offered(resolution)
    if ask.craft_slug is not None:
        return CraftChoice(craft=resolution.craft if resolution else None)
    if ask.any_craft or resolution is None or resolution.status == "NONE":
        return CraftChoice(craft=None, others=tuple(offered))
    if resolution.status == "RESOLVED":
        return CraftChoice(craft=resolution.craft, others=tuple(offered[1:]))
    if reply is None or reply.craft is None:
        return CraftChoice(craft=offered[0], others=tuple(offered[1:]))
    picked = reply.chosen(offered)
    return CraftChoice(craft=picked, others=_distinct(offered, without=picked))


def compared_choice(
    ask: UnderstandAsk, choice: CraftChoice, reply: UnderstandReply | None, offered: Sequence[CraftRef]
) -> CraftChoice:
    listed = _distinct(reply.compared(offered), without=None) if reply is not None else ()
    if ask.any_craft or len(listed) < 2:
        return choice
    slugs = [craft.slug for craft in listed]
    if ask.craft_slug is not None and (choice.craft is None or choice.craft.slug not in slugs):
        return choice
    lead = choice.craft if ask.craft_slug is not None and choice.craft is not None else listed[0]
    compared = tuple(craft for craft in listed if craft.slug != lead.slug)[:COMPARED_CRAFTS_MAX]
    kept = {lead.slug, *(craft.slug for craft in compared)}
    rest = (*([choice.craft] if choice.craft is not None else []), *choice.others)
    return CraftChoice(craft=lead, others=_distinct(rest, without=None, leaving=kept), compared=compared)


def understood_seats(
    disciplines: Sequence[str], seats: Sequence[str], *, depth: str, held: Sequence[str] | None
) -> list[str]:
    limit = depth_policy(depth).max_experts
    if depth in WIDENED_DEPTHS:
        return list(seats[:limit])
    return list(covering_seats(relevant_fields(disciplines, held), seats, limit=limit))


def asked_fields(question: str, craft: CraftRef | None, reply: UnderstandReply | None) -> list[str]:
    if reply is not None and reply.disciplines:
        return list(reply.disciplines)
    words = reply.english_question if reply is not None and reply.english_question else question
    return question_fields(words, craft.name if craft else None)


def _understanding(
    ask: UnderstandAsk, choice: CraftChoice, reading: Reading, held: Sequence[str] | None = None
) -> Understanding:
    depth = effective_depth(ask.depth, ask.role, past_degrade=reading.degraded)
    reply = reading.reply
    asked = asked_fields(ask.question, choice.craft, reply)
    return Understanding(
        craft=choice.craft,
        candidates=list(choice.others[:MAX_CANDIDATES]),
        compared=list(choice.compared) if reply else [],
        disciplines=answer_fields(asked, depth, held or ()),
        seats=understood_seats(asked, reply.seats if reply else (), depth=depth, held=held),
        depth=depth,
        language=ask.language,
        english_question=reply.english_question if reply else None,
        basis="MODEL" if reply else "RESOLVER",
        refusal=reading.refusal,
    )


def _offered(resolution: CraftResolution | None) -> list[CraftRef]:
    return [candidate.craft for candidate in resolution.candidates] if resolution else []


def _distinct(
    crafts: Sequence[CraftRef], *, without: CraftRef | None, leaving: set[str] | None = None
) -> tuple[CraftRef, ...]:
    seen = ({without.slug} if without else set()) | (leaving or set())
    kept: list[CraftRef] = []
    for craft in crafts:
        if craft.slug not in seen:
            seen.add(craft.slug)
            kept.append(craft)
    return tuple(kept)
