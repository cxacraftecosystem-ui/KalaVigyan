from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.research.stream import Emit, parse_event

__all__ = ["TRACED_EVENTS", "StepLog", "TracedStep"]

TRACED_EVENTS = frozenset({"status", "trail", "paced"})
MILLISECONDS = 1000

Clock = Callable[[], float]


@dataclass(frozen=True)
class TracedStep:
    step: str
    ms: int
    detail: Mapping[str, Any]


class StepLog:
    def __init__(self, clock: Clock = time.monotonic) -> None:
        self._clock = clock
        self._started = clock()
        self.steps: list[TracedStep] = []

    def traced(self, emit: Emit) -> Emit:
        async def traced_emit(name: str, data: Any) -> None:
            await emit(name, data)
            if name in TRACED_EVENTS:
                self.note(name, data)

        return traced_emit

    def note(self, name: str, data: Any) -> None:
        detail = parse_event(name, data).model_dump(mode="json", by_alias=True, exclude_unset=True)
        elapsed = round((self._clock() - self._started) * MILLISECONDS)
        self.steps.append(TracedStep(step=name, ms=elapsed, detail=detail))
