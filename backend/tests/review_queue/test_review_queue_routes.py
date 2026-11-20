import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import review_queue as route
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import InvalidInput
from app.main import create_app
from app.models import User
from app.research.review_queue import (
    COMPONENTS,
    FACTS,
    IMAGES,
    TESTIMONY,
    FactLevelRaise,
    QueueApproval,
    QueueDecision,
    QueueRejection,
    ReviewFilters,
    ReviewQueuePage,
)
from app.services import review_queue_decisions as decisions
from app.services.review_queue_errors import (
    DecisionConflict,
    NotYourQueue,
    OwnItem,
    UnknownCraft,
    UnknownItem,
)

ITEM = uuid.UUID(int=77)
NOW = datetime(2026, 11, 19, 12, tzinfo=UTC)
NO_SESSION: Any = None
DECIDED = QueueDecision(
    kind=FACTS, id=ITEM, status="APPROVED", level="PROVISIONAL", sources_differ=False, message="ok"
)
EMPTY = ReviewQueuePage(
    kinds=["FACTS", "TESTIMONY"], counts={"FACTS": 0, "TESTIMONY": 0}, total=0, items=[], next_cursor=None
)


class Recorded:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def person(role: str) -> User:
    return User(id=uuid.UUID(int=11), name="Asha Iyer", email="asha@example.org", role=role)


def client(role: str, session: Recorded | None = None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: person(role)

    async def opened() -> AsyncIterator[Any]:
        yield session or Recorded()

    app.dependency_overrides[get_session] = opened
    return TestClient(app)


@pytest.mark.parametrize("role", ["STUDENT", "ARTISAN", "RESEARCHER"])
def test_the_queue_refuses_an_account_that_reviews_nothing(role: str) -> None:
    assert client(role).get("/api/review-queue").status_code == 403
    assert client(role).post(f"/api/review-queue/FACTS/{ITEM}/approve", json={}).status_code == 403


def test_the_queue_hands_its_filters_to_the_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[ReviewFilters] = []

    async def listed(
        session: Any, viewer: User, filters: ReviewFilters, *, adapters: Any, now: datetime
    ) -> Any:
        seen.append(filters)
        return EMPTY

    monkeypatch.setattr(route, "list_review_queue", listed)
    query = "kind=FACTS&craft=Kutch-Ajrakh&origin=AGENT&cursor=1~" + "0" * 32 + "&limit=10"
    response = client("PROFESSOR").get(f"/api/review-queue?{query}")
    assert response.status_code == 200
    assert response.json()["kinds"] == ["FACTS", "TESTIMONY"]
    assert seen == [
        ReviewFilters(
            kind="FACTS", craft_slug="Kutch-Ajrakh", origin="AGENT", cursor="1~" + "0" * 32, limit=10
        )
    ]


@pytest.mark.parametrize("query", ["kind=PAGES", "origin=SITE", "limit=0", "limit=51", "cursor="])
def test_a_wrong_filter_is_refused_before_the_listing(query: str) -> None:
    assert client("ADMIN").get(f"/api/review-queue?{query}").status_code == 422


@pytest.mark.parametrize(
    ("error", "status"), [(UnknownCraft("x"), 404), (InvalidInput("Unknown cursor."), 422)]
)
def test_listing_refusals_become_their_statuses(
    monkeypatch: pytest.MonkeyPatch, error: Exception, status: int
) -> None:
    async def refused(*args: Any, **kwargs: Any) -> Any:
        raise error

    monkeypatch.setattr(route, "list_review_queue", refused)
    assert client("ADMIN").get("/api/review-queue").status_code == status


def test_an_approval_is_committed_and_answered(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[decisions.ItemRef, QueueApproval]] = []

    async def approved(
        session: Any, ref: decisions.ItemRef, user: User, body: QueueApproval, *, now: datetime
    ) -> Any:
        seen.append((ref, body))
        return DECIDED

    refreshed: list[QueueDecision] = []

    async def refresh(opened: Any, decision: QueueDecision) -> bool:
        refreshed.append(decision)
        return True

    monkeypatch.setattr(decisions, "approve_item", approved)
    monkeypatch.setattr(route, "refresh_after_decision", refresh)
    session = Recorded()
    response = client("ADMIN", session).post(
        f"/api/review-queue/IMAGES/{ITEM}/approve", json={"note": "Clear."}
    )
    assert response.status_code == 200 and response.json()["status"] == "APPROVED"
    assert refreshed == [DECIDED]
    assert seen == [(decisions.ItemRef(IMAGES, ITEM), QueueApproval(note="Clear."))]
    assert (session.commits, session.rollbacks) == (1, 0)


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (UnknownItem("gone"), 404),
        (OwnItem("own"), 403),
        (NotYourQueue("not yours"), 403),
        (DecisionConflict("decided"), 409),
        (InvalidInput("no version"), 422),
    ],
)
def test_decision_refusals_roll_back_and_become_their_statuses(
    monkeypatch: pytest.MonkeyPatch, error: Exception, status: int
) -> None:
    async def refused(*args: Any, **kwargs: Any) -> Any:
        raise error

    monkeypatch.setattr(decisions, "reject_item", refused)
    session = Recorded()
    response = client("ADMIN", session).post(
        f"/api/review-queue/TESTIMONY/{ITEM}/reject", json={"reason": "Misheard."}
    )
    assert response.status_code == status
    assert (session.commits, session.rollbacks) == (0, 1)


def test_a_rejection_without_a_reason_never_reaches_the_service(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[Any] = []
    monkeypatch.setattr(decisions, "reject_item", lambda *args, **kwargs: called.append(args))
    response = client("ADMIN").post(f"/api/review-queue/FACTS/{ITEM}/reject", json={"reason": "no"})
    assert response.status_code == 422 and called == []


def test_raising_and_retracting_reach_their_own_services(monkeypatch: pytest.MonkeyPatch) -> None:
    reached: list[str] = []

    def recording(name: str) -> Any:
        async def decided(session: Any, claim_id: uuid.UUID, user: User, body: Any, *, now: datetime) -> Any:
            reached.append(f"{name}:{claim_id}")
            return DECIDED

        return decided

    async def refresh(opened: Any, decision: QueueDecision) -> bool:
        reached.append(f"refresh:{decision.status}")
        return True

    monkeypatch.setattr(decisions, "raise_fact", recording("raise"))
    monkeypatch.setattr(decisions, "retract_fact", recording("retract"))
    monkeypatch.setattr(route, "refresh_after_decision", refresh)
    professor = client("PROFESSOR")
    assert professor.post(f"/api/review-queue/FACTS/{ITEM}/raise", json={}).status_code == 200
    assert (
        professor.post(f"/api/review-queue/FACTS/{ITEM}/retract", json={"reason": "Wrong."}).status_code
        == 200
    )
    assert reached == [f"raise:{ITEM}", "refresh:APPROVED", f"retract:{ITEM}", "refresh:APPROVED"]


@pytest.mark.parametrize("kind", [IMAGES, COMPONENTS])
async def test_a_professor_decides_neither_pictures_nor_components(kind: str) -> None:
    with pytest.raises(NotYourQueue):
        await decisions.approve_item(
            NO_SESSION, decisions.ItemRef(kind, ITEM), person("PROFESSOR"), QueueApproval(), now=NOW
        )
    with pytest.raises(NotYourQueue):
        rejection = QueueRejection(reason="Not for this craft.")
        await decisions.reject_item(
            NO_SESSION, decisions.ItemRef(kind, ITEM), person("PROFESSOR"), rejection, now=NOW
        )


async def test_a_researcher_neither_raises_nor_retracts_a_fact() -> None:
    with pytest.raises(NotYourQueue):
        await decisions.raise_fact(NO_SESSION, ITEM, person("RESEARCHER"), FactLevelRaise(), now=NOW)


async def test_a_testimony_decision_names_the_version_it_was_read_at() -> None:
    with pytest.raises(InvalidInput):
        await decisions.approve_item(
            NO_SESSION, decisions.ItemRef(TESTIMONY, ITEM), person("ADMIN"), QueueApproval(), now=NOW
        )


def test_a_retracted_fact_refreshes_signed_out_pages_once_it_is_committed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retracted = DECIDED.model_copy(update={"status": "RETRACTED"})
    order: list[str] = []
    session = Recorded()

    async def decided(opened: Any, claim_id: uuid.UUID, user: User, body: Any, *, now: datetime) -> Any:
        return retracted

    async def refreshed(opened: Any, decision: QueueDecision) -> bool:
        order.append(f"refresh:{decision.status}:{session.commits}")
        return True

    monkeypatch.setattr(decisions, "retract_fact", decided)
    monkeypatch.setattr(route, "refresh_after_decision", refreshed)
    path = f"/api/review-queue/FACTS/{ITEM}/retract"
    response = client("PROFESSOR", session).post(path, json={"reason": "Wrong."})
    assert response.status_code == 200
    assert order == ["refresh:RETRACTED:1"]


def test_a_refused_decision_refreshes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    refreshed: list[Any] = []

    async def refused(*args: Any, **kwargs: Any) -> Any:
        raise DecisionConflict("decided")

    async def refresh(opened: Any, decision: QueueDecision) -> bool:
        refreshed.append(decision)
        return True

    monkeypatch.setattr(decisions, "retract_fact", refused)
    monkeypatch.setattr(route, "refresh_after_decision", refresh)
    path = f"/api/review-queue/FACTS/{ITEM}/retract"
    response = client("PROFESSOR").post(path, json={"reason": "Wrong."})
    assert response.status_code == 409 and refreshed == []
