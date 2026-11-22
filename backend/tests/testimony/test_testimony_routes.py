import uuid
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.api.routes import artisan_contributions, testimony_review
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import InvalidInput
from app.models import ArtisanProfile, User
from app.research.review_queue import QueueApproval, QueueRejection
from app.services import review_queue_decisions as decisions
from app.services.review_queue_errors import DecisionConflict

from . import fakes


def person(role: str, user_id: uuid.UUID = fakes.USER) -> User:
    return User(
        id=user_id, email=f"{role.lower()}@example.org", name="Bilal Khatri", role=role, twoFactorEnabled=True
    )


@pytest.fixture
def state() -> dict[str, object]:
    return {}


@pytest.fixture
def app(state: dict[str, object]) -> Iterator[FastAPI]:
    built = FastAPI()
    built.include_router(testimony_review.router, prefix="/api")
    built.include_router(artisan_contributions.router, prefix="/api")

    async def session() -> AsyncIterator[object]:
        yield state["session"]

    built.dependency_overrides[get_session] = session
    built.dependency_overrides[get_current_user] = lambda: state["user"]
    yield built


async def call(app: FastAPI, method: str, path: str, **options: object) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **options)


async def test_the_review_queue_is_refused_to_artisans_and_researchers(
    app: FastAPI, state: dict[str, object]
) -> None:
    state["session"] = fakes.FakeSession()
    for role in ("STUDENT", "ARTISAN", "RESEARCHER"):
        state["user"] = person(role)
        response = await call(app, "GET", "/api/testimony/review")
        assert response.status_code == 403, role
        assert response.json() == {
            "detail": "Reviewing artisans' contributions is for professors and admins."
        }


def queued(item: object) -> decisions.ItemRef:
    return decisions.ItemRef("TESTIMONY", item.id)  # type: ignore[attr-defined]


async def test_a_stale_version_is_refused_with_the_reload_sentence() -> None:
    item = fakes.contribution(version=3)
    reviewer = person("PROFESSOR", fakes.REVIEWER)
    with pytest.raises(
        DecisionConflict, match=r"Someone changed this testimony since it was read. Reload it."
    ):
        await decisions.approve_item(
            fakes.session_for(item), queued(item), reviewer, QueueApproval(version=2), now=fakes.at(9)
        )


async def test_a_held_back_name_blocks_approval_and_names_the_problem() -> None:
    item = fakes.contribution(english="Khatri and I wash the cloth after the alum")
    session = fakes.session_for(item)
    session.rows[(User, fakes.USER)] = person("ARTISAN")
    session.rows[(ArtisanProfile, fakes.USER)] = fakes.profile(
        creditMode="FIRST_NAME", creditShortName="Bilal"
    )
    reviewer = person("PROFESSOR", fakes.REVIEWER)
    with pytest.raises(InvalidInput) as refused:
        await decisions.approve_item(
            session, queued(item), reviewer, QueueApproval(version=2), now=fakes.at(9)
        )
    assert refused.value.problems == [  # type: ignore[attr-defined]
        "a held-back name is in the quote, the English or the claim; edit it out first"
    ]
    assert item.status == "PENDING"


async def test_a_quote_not_in_english_needs_its_english_before_approval() -> None:
    item = fakes.contribution(english=None)
    reviewer = person("ADMIN", fakes.REVIEWER)
    with pytest.raises(InvalidInput, match="a quote not in English needs its English"):
        await decisions.approve_item(
            fakes.session_for(item), queued(item), reviewer, QueueApproval(version=2), now=fakes.at(9)
        )


async def test_a_rejection_of_other_needs_a_note() -> None:
    item = fakes.contribution()
    reviewer = person("PROFESSOR", fakes.REVIEWER)
    rejection = QueueRejection(version=2, testimony_reason="OTHER")
    with pytest.raises(InvalidInput, match="a reason of OTHER needs a note"):
        await decisions.reject_item(
            fakes.session_for(item), queued(item), reviewer, rejection, now=fakes.at(9)
        )


def test_unknown_fields_are_refused_in_a_review_body() -> None:
    with pytest.raises(ValidationError):
        QueueApproval.model_validate({"version": 2, "level": "VERIFIED"})


@pytest.mark.parametrize("final", ["REJECTED", "WITHDRAWN"])
async def test_a_final_contribution_cannot_be_taken_back(
    app: FastAPI, state: dict[str, object], final: str
) -> None:
    item = fakes.contribution(
        status=final, rejectReason="UNCLEAR", rejectedAt=fakes.at(8), withdrawnAt=fakes.at(8)
    )
    state["user"], state["session"] = person("ARTISAN"), fakes.session_for(item)
    response = await call(app, "POST", f"/api/artisan/contributions/{item.id}/withdraw")
    assert response.status_code == 409
    assert state["session"].rolled_back


async def test_another_accounts_contribution_is_not_found(app: FastAPI, state: dict[str, object]) -> None:
    item = fakes.contribution()
    state["user"], state["session"] = person("ARTISAN", fakes.OTHER_USER), fakes.session_for(item)
    for method, path in (
        ("POST", f"/api/artisan/contributions/{item.id}/withdraw"),
        ("GET", f"/api/artisan/contributions/{item.id}/audio"),
        ("GET", f"/api/artisan/conversations/{fakes.CONVERSATION}"),
        ("DELETE", f"/api/artisan/conversations/{fakes.CONVERSATION}"),
    ):
        response = await call(app, method, path)
        assert response.status_code == 404, path


async def test_withdrawing_needs_no_capability_only_ownership(app: FastAPI, state: dict[str, object]) -> None:
    item = fakes.contribution(status="REJECTED", rejectReason="UNCLEAR", rejectedAt=fakes.at(8))
    state["user"], state["session"] = person("STUDENT"), fakes.session_for(item)
    response = await call(app, "POST", f"/api/artisan/contributions/{item.id}/withdraw")
    assert response.status_code == 409
