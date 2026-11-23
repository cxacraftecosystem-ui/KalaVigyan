from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from dataclasses import replace

from app.composer.drafts import DraftSentence
from app.composer.expert_takes import SeatAsk, SeatTake, compose_retake
from app.research.composition import ComposedSentence
from app.research.structured import StructuredModel

from .answer_events import CitedClaims
from .expert_view_blocks import Take
from .section_blocks import KeptSentence, prose_problems

__all__ = [
    "PROSE_CHECK",
    "RETAKE_LEAVES_SECONDS",
    "RETAKE_SECONDS",
    "failed_sentences",
    "kept_takes",
    "retake_allowed",
    "retaken_takes",
]

logger = logging.getLogger(__name__)

PROSE_CHECK = "PROSE_CHECK"
RETAKE_SECONDS = 20.0
RETAKE_LEAVES_SECONDS = 20.0


def retake_allowed(seconds_left: float) -> bool:
    return seconds_left >= RETAKE_SECONDS + RETAKE_LEAVES_SECONDS


def failed_sentences(take: SeatTake, cited: CitedClaims) -> tuple[DraftSentence, ...]:
    return tuple(failed for sentence in take.sentences if (failed := _failed(sentence, cited)) is not None)


def kept_takes(takes: Sequence[SeatTake], cited: CitedClaims) -> dict[str, Take]:
    return {take.seat: kept for take in takes if (kept := _kept_take(take, cited)) is not None}


async def retaken_takes(
    model: StructuredModel, asks: Sequence[SeatAsk], takes: Sequence[SeatTake], cited: CitedClaims
) -> list[SeatTake]:
    failing = {
        take.seat: found for take in takes if take.sentences and (found := failed_sentences(take, cited))
    }
    chosen = [ask for ask in asks if ask.seat.seat in failing]
    if not chosen:
        return list(takes)
    try:
        async with asyncio.timeout(RETAKE_SECONDS):
            replies = await asyncio.gather(
                *(compose_retake(model, ask, failing[ask.seat.seat]) for ask in chosen),
                return_exceptions=True,
            )
    except TimeoutError:
        logger.warning(
            "the retakes of %s took over %s s; their views are dropped", sorted(failing), RETAKE_SECONDS
        )
        return list(takes)
    again = _answered(chosen, replies)
    return [again.get(take.seat, take) for take in takes]


def _answered(asks: Sequence[SeatAsk], replies: Sequence[object]) -> Mapping[str, SeatTake]:
    again: dict[str, SeatTake] = {}
    for ask, reply in zip(asks, replies, strict=True):
        if isinstance(reply, SeatTake):
            again[reply.seat] = reply
        elif isinstance(reply, Exception):
            logger.warning("the %s view is not taken again: %s", ask.seat.seat, reply)
        elif isinstance(reply, BaseException):
            raise reply
    return again


def _failed(sentence: DraftSentence, cited: CitedClaims) -> DraftSentence | None:
    if not sentence.passes or sentence.sentence is None:
        return sentence
    problems = prose_problems([_kept(sentence.sentence)], cited)
    if not problems:
        return None
    return replace(sentence, problems=tuple(f"{PROSE_CHECK}: {problem}" for problem in problems))


def _kept_take(take: SeatTake, cited: CitedClaims) -> Take | None:
    failed = failed_sentences(take, cited)
    if not take.sentences or failed:
        described = " | ".join(f"{s.raw_text!r}: {'; '.join(s.problems) or 'unreadable'}" for s in failed)
        logger.warning("the %s view is dropped: %s", take.seat, described or "no sentence")
        return None
    return tuple(_kept(s.sentence) for s in take.sentences if s.sentence is not None)


def _kept(sentence: ComposedSentence) -> KeptSentence:
    return KeptSentence(sentence.text, tuple(sentence.claim_ids), tuple(sentence.evidence_ids), False)
