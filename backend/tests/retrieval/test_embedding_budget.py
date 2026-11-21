import uuid
from typing import Any

import pytest

from app.core.errors import InvalidInput
from app.models import Claim
from app.research.embedding import EMBEDDING_DIMENSIONS
from app.retrieval.deadline import Deadline
from app.retrieval.indexing import _fill, _Pending


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class Written:
    rowcount = 1


class Session:
    def __init__(self) -> None:
        self.updates = 0

    async def execute(self, statement: Any) -> Written:
        self.updates += 1
        return Written()

    async def commit(self) -> None:
        return None


def test_a_deadline_passes_once_its_seconds_are_spent() -> None:
    clock = Clock()
    deadline = Deadline.after(30, clock=clock)
    assert deadline.at == 130.0 and not deadline.passed()
    clock.now = 129.9
    assert not deadline.passed()
    clock.now = 130.0
    assert deadline.passed()


def test_a_time_budget_must_be_positive() -> None:
    with pytest.raises(InvalidInput):
        Deadline.after(0)


async def test_filling_vectors_starts_no_batch_after_the_deadline() -> None:
    clock = Clock()
    deadline = Deadline.after(10, clock=clock)
    session = Session()
    pending = [_Pending(id=uuid.uuid4(), text=f"claim {n}", read=f"claim {n}") for n in range(5)]
    batches: list[list[str]] = []

    async def embed(texts: list[str]) -> list[list[float]]:
        batches.append(texts)
        clock.now += 6
        return [[0.0] * EMBEDDING_DIMENSIONS for _ in texts]

    done = await _fill(session, embed, Claim, pending, batch_size=2, deadline=deadline)
    assert done == 4
    assert batches == [["claim 0", "claim 1"], ["claim 2", "claim 3"]]
    assert session.updates == 4
