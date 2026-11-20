import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import contribution_streams
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import Refused
from app.main import create_app
from app.models import User
from app.research.contribution_queue import BatchItem
from app.services import contribution_queue
from app.services.contribution_queue import QueuedFact

from ..knowledge_writes.fakes import PAGE_URL, QUOTE, STATEMENT

PROPOSAL = {
    "subject": {"kind": "craft", "slug": "Kutch-Ajrakh"},
    "field": "PROCESS",
    "statement": STATEMENT,
    "sources": [{"url": PAGE_URL, "title": "Indigo in Ajrakh", "quotes": [{"text": QUOTE}]}],
}


class FakeSession:
    def __init__(self) -> None:
        self.ended: list[str] = []

    async def commit(self) -> None:
        self.ended.append("commit")

    async def rollback(self) -> None:
        self.ended.append("rollback")


def person(role: str) -> User:
    return User(id=uuid.UUID(int=91), name=role.title(), email="p@example.org", role=role)


def client(user: User, session: FakeSession) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user

    async def opened() -> AsyncIterator[Any]:
        yield session

    app.dependency_overrides[get_session] = opened
    return TestClient(app)


def never_called(*_: Any, **__: Any) -> Any:
    raise AssertionError("the work ran")


def test_a_ledger_range_that_runs_backwards_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(contribution_streams.cost_ledger, "cost_ledger", never_called)
    response = client(person("ADMIN"), FakeSession()).get(
        "/api/knowledge/contribution-costs", params={"from": "2026-11-20", "to": "2026-11-19"}
    )
    assert response.status_code == 422 and "ends before it starts" in response.json()["detail"]


def test_queued_facts_need_the_contribution_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    async def refused(session: Any, user: User) -> None:
        raise Refused("terms_needed", "Accept the contribution terms first.")

    monkeypatch.setattr(contribution_streams, "require_terms", refused)
    monkeypatch.setattr(contribution_streams.contribution_queue, "enqueue_facts", never_called)
    body = {"facts": [{"idempotencyKey": "site-form:0001", "proposal": PROPOSAL}]}
    response = client(person("RESEARCHER"), FakeSession()).post("/api/knowledge/proposals/facts", json=body)
    assert response.status_code == 403 and response.json()["detail"] == "Accept the contribution terms first."


def test_a_batch_is_queued_with_the_contribution_origin_and_committed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[list[QueuedFact], str]] = []

    async def accepted(session: Any, user: User) -> None:
        return None

    async def enqueue(
        session: Any, user: User, facts: list[QueuedFact], *, origin: str, now: datetime
    ) -> Any:
        seen.append((list(facts), origin))
        return contribution_queue.batch_of(
            [
                BatchItem(index=fact.index, accepted=False, idempotency_key=fact.key, problem="Spent.")
                for fact in facts
            ]
        )

    monkeypatch.setattr(contribution_streams, "require_terms", accepted)
    monkeypatch.setattr(contribution_streams.contribution_queue, "enqueue_facts", enqueue)
    session = FakeSession()
    body = {"facts": [{"idempotencyKey": "site-form:0001", "proposal": PROPOSAL}, {"proposal": PROPOSAL}]}
    response = client(person("RESEARCHER"), session).post("/api/knowledge/proposals/facts", json=body)
    assert response.status_code == 200, response.text
    assert [(item["index"], item["idempotencyKey"]) for item in response.json()["items"]] == [
        (0, "site-form:0001"),
        (1, None),
    ]
    ((facts, origin),) = seen
    assert (origin, [fact.key for fact in facts]) == ("CONTRIBUTION", ["site-form:0001", None])
    assert session.ended == ["commit"]


def test_a_student_cannot_steward_or_read_the_ledger() -> None:
    student = client(person("STUDENT"), FakeSession())
    assert student.put("/api/knowledge/stewardship/Kutch-Ajrakh").status_code == 403
    assert student.get("/api/knowledge/contribution-costs").status_code == 403
