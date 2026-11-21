from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from .open_work import TASK_PROMPTS, OpenTask, TaskSubject, task_key
from .open_work_gap_keys import GAP_TASK, gap_detail
from .open_work_gaps import (
    ACCEPTED_FACTS_MIN,
    ASKED_WINDOW,
    FAILED_QUOTE,
    FEW_SENTENCES,
    FIELD_SENTENCES_MIN,
    LOW_RETRIEVAL,
    MISSING_FIELD,
    NO_CITED_EVIDENCE,
)
from .open_work_texts import counted

__all__ = ["LACK_PHRASES", "OpenGap", "gap_acceptance", "gap_needed", "gap_task", "listed"]

LACK_PHRASES: Mapping[str, str] = MappingProxyType(
    {
        NO_CITED_EVIDENCE: "found no cited evidence",
        MISSING_FIELD: "left a field it needed without a cited sentence",
        FEW_SENTENCES: f"held fewer than {FIELD_SENTENCES_MIN} cited sentences in a field",
        LOW_RETRIEVAL: "found no stored fact matching the question's words or names",
        FAILED_QUOTE: "cited a fact whose quote failed its check",
    }
)


@dataclass(frozen=True)
class OpenGap:
    id: uuid.UUID
    question: str
    askers: int
    last_asked: datetime
    fields: tuple[str, ...]
    lacks: tuple[str, ...]
    priority: str


def gap_task(subject: TaskSubject, gap: OpenGap) -> OpenTask:
    return OpenTask(
        key=task_key(GAP_TASK, subject, gap_detail(gap.id)),
        kind=GAP_TASK,
        priority=gap.priority,
        subject=subject,
        field=gap.fields[0],
        needed=gap_needed(gap),
        acceptance=gap_acceptance(subject.name, gap.fields),
        count=gap.askers,
        prompt=TASK_PROMPTS[GAP_TASK],
    )


def gap_needed(gap: OpenGap) -> str:
    lacked = listed([LACK_PHRASES[lack] for lack in gap.lacks])
    return (
        f'Readers asked "{gap.question}" ({counted(gap.askers, "reader")} in the last {ASKED_WINDOW.days} days, '
        f"the latest on {gap.last_asked.date().isoformat()}); the answer {lacked}. "
        f"Cited facts under {listed(gap.fields)} would answer it."
    )


def gap_acceptance(name: str, fields: Sequence[str]) -> str:
    return (
        f"At least {ACCEPTED_FACTS_MIN} cited facts of {name} under each of {listed(fields)} that a retrieval run "
        "for the question finds, each one sentence saying no more than its verbatim quotes. "
        "Propose them with propose_facts, naming the field's MISSING_FIELD or THIN_FIELD task as task_key when one "
        "is open and no task_key otherwise. The task closes itself, and its reservation ends COMPLETED, when the "
        "nightly retrieval run finds them."
    )


def listed(items: Sequence[str]) -> str:
    if len(items) < 2:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"
