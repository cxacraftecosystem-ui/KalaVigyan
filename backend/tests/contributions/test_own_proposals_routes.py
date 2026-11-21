import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import own_proposals as routes
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import InvalidInput, Refused
from app.main import create_app
from app.models import User
from app.research.component_proposals import WAYS_ON, ComponentMatch, ComponentProposalResult
from app.research.knowledge_api import ComponentSummary, CraftComponents
from app.research.own_proposals import ComponentProposalBody, OwnProposal, TermsStatus
from app.services.own_proposals import TERMS_NEEDED, UnknownProposal

PROPOSAL = {
    "label": "kutch-ajrakh/chemistry/indigo-vat-redox",
    "title": "The indigo vat's reduction",
    "description": "Shows indigo reduced to pale yellow leucoindigo in the vat and blued again in the air.",
    "kind": "reaction_player",
    "field": "CHEMISTRY",
    "craftSlug": "Kutch-Ajrakh",
    "subjects": [{"kind": "CRAFT", "key": "Kutch-Ajrakh"}],
    "consideredLabels": [],
}
HELD = ComponentSummary(
    label="kutch-ajrakh/chemistry/indigo-vat",
    title="The indigo vat",
    description="The vat's reduction and the air's oxidation of indigo, step by step.",
    kind="reaction_player",
    field="CHEMISTRY",
    fields=[],
    craft_slug="Kutch-Ajrakh",
    subjects=[],
)
WAITING = OwnProposal(
    id=uuid.UUID(int=7),
    kind="FACT",
    state="WITHDRAWN",
    status="WITHDRAWN",
    text="Ajrakh cloth is dipped in the indigo vat four times.",
    field="PROCESS",
    subject_name="Kutch Ajrakh",
    craft_slug="Kutch-Ajrakh",
    created_at=datetime(2026, 11, 19, 10, tzinfo=UTC),
)


class Recorded:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def client(role: str, session: Recorded) -> TestClient:
    app = create_app()
    user = User(id=uuid.UUID(int=11), name="Asha Iyer", email="asha@example.org", role=role)
    app.dependency_overrides[get_current_user] = lambda: user

    async def opened() -> AsyncIterator[Any]:
        yield session

    app.dependency_overrides[get_session] = opened
    return TestClient(app)


def answering(outcome: Any, seen: list[Any]) -> Any:
    async def answer(*args: Any, **kwargs: Any) -> Any:
        seen.append((args, kwargs))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return answer


def test_a_student_may_not_propose_a_component() -> None:
    session = Recorded()
    response = client("STUDENT", session).post("/api/contributions/proposals/components", json=PROPOSAL)
    assert response.status_code == 403 and session.commits == 0


def test_a_close_match_comes_back_with_its_matches_and_the_two_ways_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refused = ComponentProposalResult(
        outcome="REFUSED",
        label=PROPOSAL["label"],
        message="1 component in the library already shows this; nothing was stored.",
        matches=[
            ComponentMatch(component=HELD, reasons=["the same kind, keyed to the same craft Kutch Ajrakh"])
        ],
        ways_on=list(WAYS_ON),
    )
    seen: list[Any] = []
    monkeypatch.setattr(routes.own_proposals, "propose_on_site", answering(refused, seen))
    session = Recorded()
    response = client("RESEARCHER", session).post("/api/contributions/proposals/components", json=PROPOSAL)
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["outcome"], body["proposalId"], len(body["waysOn"])) == ("REFUSED", None, 2)
    assert body["matches"][0]["component"]["craftSlug"] == "Kutch-Ajrakh"
    ((args, kwargs),) = seen
    draft = args[2]
    assert isinstance(draft, ComponentProposalBody) and draft.craft_slug == "Kutch-Ajrakh"
    assert isinstance(kwargs["now"], datetime)


def test_a_proposal_without_the_terms_is_refused_and_nothing_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    needed = Refused(TERMS_NEEDED, "Accept the contribution terms, version 2026-11-19, before you propose.")
    monkeypatch.setattr(routes.own_proposals, "propose_on_site", answering(needed, []))
    session = Recorded()
    response = client("RESEARCHER", session).post("/api/contributions/proposals/components", json=PROPOSAL)
    assert response.status_code == 409
    assert response.json()["detail"].startswith("Accept the contribution terms")
    assert (session.commits, session.rollbacks) == (0, 1)


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (UnknownProposal("No proposal of yours has that id."), 404),
        (Refused("not_waiting", "It is published, and a published contribution stays published."), 409),
    ],
)
def test_a_withdrawal_that_cannot_happen_says_why(
    monkeypatch: pytest.MonkeyPatch, error: Exception, status: int
) -> None:
    monkeypatch.setattr(routes.own_proposals, "withdraw_fact", answering(error, []))
    session = Recorded()
    response = client("RESEARCHER", session).post(
        f"/api/contributions/proposals/facts/{uuid.UUID(int=7)}/withdraw"
    )
    assert response.status_code == status and session.commits == 0


def test_a_withdrawn_fact_is_committed_and_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Any] = []
    monkeypatch.setattr(routes.own_proposals, "withdraw_fact", answering(WAITING, seen))
    session = Recorded()
    response = client("RESEARCHER", session).post(
        f"/api/contributions/proposals/facts/{uuid.UUID(int=7)}/withdraw"
    )
    assert response.status_code == 200 and session.commits == 1
    assert (response.json()["state"], response.json()["subjectName"]) == ("WITHDRAWN", "Kutch Ajrakh")
    ((args, _),) = seen
    assert args[2] == uuid.UUID(int=7)


def test_the_library_search_takes_its_words_craft_and_kind_from_the_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Any] = []
    found = CraftComponents(
        craft_slug="Kutch-Ajrakh", field=None, kind="reaction_player", query="vat", components=[HELD]
    )
    monkeypatch.setattr(routes.component_library, "library_components", answering(found, seen))
    response = client("RESEARCHER", Recorded()).get(
        "/api/contributions/proposals/library",
        params={"query": "vat", "craftSlug": "Kutch-Ajrakh", "kind": "reaction_player"},
    )
    assert response.status_code == 200, response.text
    assert [component["label"] for component in response.json()["components"]] == [HELD.label]
    ((_, kwargs),) = seen
    assert kwargs == {"slug": "Kutch-Ajrakh", "field": None, "kind": "reaction_player", "query": "vat"}


def test_an_unknown_craft_or_kind_in_the_library_search_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    unknown = InvalidInput("No craft has the slug 'Nowhere'.")
    monkeypatch.setattr(routes.component_library, "library_components", answering(unknown, []))
    searched = client("RESEARCHER", Recorded())
    assert (
        searched.get("/api/contributions/proposals/library", params={"craftSlug": "Nowhere"}).status_code
        == 422
    )
    assert searched.get("/api/contributions/proposals/library", params={"kind": "guess"}).status_code == 422


def test_the_form_offers_the_terms_every_field_every_kind_and_what_each_need_takes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unaccepted(session: Any, user: User) -> TermsStatus:
        return TermsStatus(version="2026-11-19", accepted_at=None)

    monkeypatch.setattr(routes.own_proposals, "terms_status", unaccepted)
    response = client("RESEARCHER", Recorded()).get("/api/contributions/proposals/form")
    assert response.status_code == 200, response.text
    form = response.json()
    assert form["terms"] == {"version": "2026-11-19", "acceptedAt": None}
    assert len(form["fields"]) == 16
    assert form["fields"][0] == {
        "field": "OVERVIEW",
        "title": "What it is",
        "covers": "what the craft is, where and by whom it is practised",
        "chapter": form["fields"][0]["chapter"],
    }
    assert {"what_if", "molecule_3d", "reaction_player", "chart", "drawing"} <= set(form["kinds"])
    assert not {"language_switch", "credits", "citation_tool", "picture_plate"} & set(form["kinds"])
    assert form["subjectKinds"] == ["CRAFT", "CONCEPT", "PLACE", "COMPOUND"]
    assert (form["needs"]["molecules"], form["needs"]["what-if"]) == (
        ["molecule_3d"],
        ["what_if", "experiment_lab"],
    )
    assert form["needs"]["map"][-1] == "map_sequence"
    assert form["needs"]["pictures"] == ["images", "picture_plate", "specimen_plate"]


def test_terms_of_another_version_are_refused_before_anything_is_stored() -> None:
    session = Recorded()
    response = client("RESEARCHER", session).post(
        "/api/contributions/proposals/terms", json={"version": "2025-01-01"}
    )
    assert response.status_code == 422 and session.commits == 0
