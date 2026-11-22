from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.research.vocabulary import CANONICAL_LANGUAGE

from .eval_floors import FloorCheck, broken
from .evaluation import SetReport
from .golden import GeneratedQuestion
from .question_writing import seeded_rank

__all__ = [
    "EXIT_BELOW_FLOOR",
    "EXIT_PASSED",
    "EXIT_WARNED",
    "NO_GENERATED",
    "RELEASE_PER_CRAFT",
    "RELEASE_SAMPLE_MAX",
    "RELEASE_SECONDS",
    "RELEASE_SEED",
    "RERANK_FAILED",
    "TIMED_OUT",
    "ReleaseCheck",
    "ReleaseVerdict",
    "release_sample",
    "rerank_warnings",
]

RELEASE_SAMPLE_MAX = 400
RELEASE_PER_CRAFT = 2
RELEASE_SEED = 400
RELEASE_SECONDS = 180
EXIT_PASSED = 0
EXIT_WARNED = 2
EXIT_BELOW_FLOOR = 3
NO_GENERATED = "no generated questions are kept, so only the hand-written questions were scored"
TIMED_OUT = "the time budget ran out before every question was asked, so no floor was compared"
RERANK_FAILED = (
    "the rerank failed for {count} of {questions} questions of {name}, which kept the fused order, "
    "so the reranked floors of {name} were not compared"
)


class ReleaseVerdict(StrEnum):
    PASSED = "PASSED"
    WARNED = "WARNED"
    BELOW_FLOOR = "BELOW_FLOOR"


EXIT_CODES: Mapping[ReleaseVerdict, int] = {
    ReleaseVerdict.PASSED: EXIT_PASSED,
    ReleaseVerdict.WARNED: EXIT_WARNED,
    ReleaseVerdict.BELOW_FLOOR: EXIT_BELOW_FLOOR,
}


@dataclass(frozen=True)
class ReleaseCheck:
    reports: Mapping[str, SetReport] = field(default_factory=dict)
    checks: tuple[FloorCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    error: str | None = None

    @property
    def complete(self) -> bool:
        return self.error is None and all(report.complete for report in self.reports.values())

    @property
    def verdict(self) -> ReleaseVerdict:
        if not self.complete:
            return ReleaseVerdict.WARNED
        if broken(self.checks):
            return ReleaseVerdict.BELOW_FLOOR
        return ReleaseVerdict.WARNED if self.all_warnings() else ReleaseVerdict.PASSED

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.verdict]

    def all_warnings(self) -> tuple[str, ...]:
        timed_out = (TIMED_OUT,) if self.error is None and not self.complete else ()
        return (*self.warnings, *rerank_warnings(self.reports), *timed_out)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.verdict is not ReleaseVerdict.BELOW_FLOOR,
            "verdict": self.verdict.value,
            "complete": self.complete,
            "warnings": list(self.all_warnings()),
            "error": self.error,
            "sets": {name: report.summary() for name, report in self.reports.items()},
            "floors": [check.as_dict() for check in self.checks],
        }


def rerank_warnings(reports: Mapping[str, SetReport]) -> tuple[str, ...]:
    return tuple(
        RERANK_FAILED.format(count=len(report.fell_back), questions=len(report.reranked.results), name=name)
        for name, report in reports.items()
        if report.fell_back
    )


def release_sample(
    generated: Sequence[GeneratedQuestion], *, hand_written: int, seed: int = RELEASE_SEED
) -> tuple[GeneratedQuestion, ...]:
    room = max(0, RELEASE_SAMPLE_MAX - hand_written)
    by_craft: dict[str, list[GeneratedQuestion]] = defaultdict(list)
    for question in generated:
        if question.language == CANONICAL_LANGUAGE:
            by_craft[question.craft_slug].append(question)
    picked: list[GeneratedQuestion] = []
    for slug in sorted(by_craft, key=lambda craft: seeded_rank(seed, "craft", craft)):
        chosen = sorted(by_craft[slug], key=lambda question: seeded_rank(seed, question.key))[
            :RELEASE_PER_CRAFT
        ]
        if len(picked) + len(chosen) > room:
            break
        picked += chosen
    return tuple(picked)
