from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.errors import InvalidInput
from app.models.answer_gaps import ANSWER_VERDICTS, GAP_LACKS
from app.models.enums import DISCIPLINES

from .open_work import PRIORITIES
from .retrieval import KnowledgeHits
from .vocabulary import FACT_LEVELS

__all__ = [
    "ACCEPTED_FACTS_MIN",
    "ANSWERED",
    "ASKED_WINDOW",
    "FAILED_QUOTE",
    "FEW_SENTENCES",
    "FIELD_SENTENCES_MIN",
    "GAP_VERDICTS",
    "GROUP_DISTANCE_MAX",
    "HIGH_ASKERS",
    "LOW_RETRIEVAL",
    "MEDIUM_ASKERS",
    "MISSING_FIELD",
    "NO_CITED_EVIDENCE",
    "RECENT_WINDOW",
    "THIN",
    "UNANSWERED",
    "Asked",
    "FieldReading",
    "GapCount",
    "Verdict",
    "accepted",
    "answer_verdict",
    "found_facts",
    "gap_count",
    "gap_priority",
    "nearest_gap",
]

ANSWERED, THIN, UNANSWERED = ANSWER_VERDICTS
GAP_VERDICTS = (THIN, UNANSWERED)
NO_CITED_EVIDENCE, MISSING_FIELD, FEW_SENTENCES, LOW_RETRIEVAL, FAILED_QUOTE = GAP_LACKS
HIGH, MEDIUM, LOW = PRIORITIES
FIELD_SENTENCES_MIN = 3
ASKED_WINDOW = timedelta(days=90)
RECENT_WINDOW = timedelta(days=30)
HIGH_ASKERS = 5
MEDIUM_ASKERS = 2
GROUP_DISTANCE_MAX = 0.15
ACCEPTED_FACTS_MIN = 2
FIELD_RANK = {discipline: rank for rank, discipline in enumerate(DISCIPLINES)}
LACK_RANK = {lack: rank for rank, lack in enumerate(GAP_LACKS)}


@dataclass(frozen=True)
class FieldReading:
    field: str
    sentences: int
    retrieval_low: bool = False
    claim_ids: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True)
class Verdict:
    verdict: str
    fields: tuple[str, ...]
    lacking: tuple[str, ...]
    lacks: tuple[str, ...]
    sentences: int


@dataclass(frozen=True)
class Asked:
    asker: str
    asked_at: datetime
    lacking: tuple[str, ...]
    lacks: tuple[str, ...]


@dataclass(frozen=True)
class GapCount:
    askers: int
    last_asked: datetime | None
    fields: tuple[str, ...]
    lacks: tuple[str, ...]


def answer_verdict(readings: Sequence[FieldReading], failed: frozenset[uuid.UUID] = frozenset()) -> Verdict:
    merged = _merged(readings)
    fields = tuple(merged)
    sentences = sum(reading.sentences for reading in merged.values())
    if sentences == 0:
        return Verdict(UNANSWERED, fields, fields, (NO_CITED_EVIDENCE,), 0)
    lacks_by_field = {field: _field_lacks(reading, failed) for field, reading in merged.items()}
    lacking = tuple(field for field, lacks in lacks_by_field.items() if lacks)
    lacks = _ordered_lacks(lack for found in lacks_by_field.values() for lack in found)
    return Verdict(THIN if lacking else ANSWERED, fields, lacking, lacks, sentences)


def gap_count(asked: Iterable[Asked], *, now: datetime) -> GapCount:
    recent = [item for item in asked if now - item.asked_at <= ASKED_WINDOW]
    if not recent:
        return GapCount(askers=0, last_asked=None, fields=(), lacks=())
    fields = {field for item in recent for field in item.lacking}
    return GapCount(
        askers=len({item.asker for item in recent}),
        last_asked=max(item.asked_at for item in recent),
        fields=tuple(sorted(fields, key=FIELD_RANK.__getitem__)),
        lacks=_ordered_lacks(lack for item in recent for lack in item.lacks),
    )


def gap_priority(askers: int, last_asked: datetime, *, now: datetime) -> str:
    recent = now - last_asked <= RECENT_WINDOW
    if askers >= HIGH_ASKERS and recent:
        return HIGH
    if askers >= HIGH_ASKERS or (askers >= MEDIUM_ASKERS and recent):
        return MEDIUM
    return LOW


def nearest_gap(distances: Mapping[uuid.UUID, float]) -> uuid.UUID | None:
    if not distances:
        return None
    gap, distance = min(distances.items(), key=lambda item: (item[1], str(item[0])))
    return gap if distance <= GROUP_DISTANCE_MAX else None


def found_facts(hits: KnowledgeHits, *, by_meaning: bool) -> int:
    return sum(
        1
        for hit in hits.claims
        if hit.level in FACT_LEVELS
        and (by_meaning or hit.lexical_rank is not None or hit.entity_rank is not None)
    )


def accepted(found: Mapping[str, int]) -> bool:
    return bool(found) and all(count >= ACCEPTED_FACTS_MIN for count in found.values())


def _merged(readings: Sequence[FieldReading]) -> dict[str, FieldReading]:
    if not readings:
        raise InvalidInput("An answer is judged by the fields it was asked to answer; none were given")
    merged: dict[str, FieldReading] = {}
    for reading in readings:
        if reading.field not in FIELD_RANK:
            raise InvalidInput(f"{reading.field!r} is not one of the sixteen fields")
        held = merged.get(reading.field)
        merged[reading.field] = reading if held is None else _joined(held, reading)
    return {field: merged[field] for field in sorted(merged, key=FIELD_RANK.__getitem__)}


def _joined(first: FieldReading, second: FieldReading) -> FieldReading:
    return FieldReading(
        field=first.field,
        sentences=first.sentences + second.sentences,
        retrieval_low=first.retrieval_low and second.retrieval_low,
        claim_ids=tuple(dict.fromkeys((*first.claim_ids, *second.claim_ids))),
    )


def _field_lacks(reading: FieldReading, failed: frozenset[uuid.UUID]) -> tuple[str, ...]:
    found = []
    if reading.sentences == 0:
        found.append(MISSING_FIELD)
    elif reading.sentences < FIELD_SENTENCES_MIN:
        found.append(FEW_SENTENCES)
    if reading.retrieval_low:
        found.append(LOW_RETRIEVAL)
    if failed.intersection(reading.claim_ids):
        found.append(FAILED_QUOTE)
    return tuple(found)


def _ordered_lacks(lacks: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(lacks), key=LACK_RANK.__getitem__))
