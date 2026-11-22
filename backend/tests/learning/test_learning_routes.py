import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import learning_views
from app.core.db import get_session
from app.main import create_app
from app.models import Craft, User
from app.models.enums import DISCIPLINES
from app.research.craft_compare import CraftComparison
from app.research.explainer import Explainer
from app.research.quiz import ExplainerQuiz, explainer_quiz
from app.research.shared_science import SharedConcept, SharedScience
from app.services import answer_quiz, knowledge_view

from ..contracts.explainer_golden import DOCUMENT, golden_json
from ..contracts.learning_golden import SHARED_SCIENCE, learning
from ..readers import sign_in_as

READER = User(id=uuid.UUID(int=7), name="Meera Rao", email="meera@example.org", role="STUDENT")
SOMEONE_ELSE = uuid.UUID(int=8)
DOCUMENT_ID = uuid.UUID(golden_json(DOCUMENT)["answerId"])
CRAFTS = {
    "Kutch-Ajrakh": Craft(id=uuid.UUID(int=1), slug="Kutch-Ajrakh", name="Kutch Ajrakh"),
    "Bagru-Hand-Block-Print": Craft(
        id=uuid.UUID(int=2), slug="Bagru-Hand-Block-Print", name="Bagru Hand Block Print"
    ),
    "Old-Ajrakh": Craft(id=uuid.UUID(int=1), slug="Kutch-Ajrakh", name="Kutch Ajrakh"),
}


@dataclass
class Stored:
    owner: uuid.UUID = READER.id
    asked: list[Any] = field(default_factory=list)


@dataclass
class AnswerSession:
    stored: Stored

    async def scalar(self, statement: Any) -> Any:
        if set(statement.compile().params.values()) == {DOCUMENT_ID, self.stored.owner}:
            return {"explainer": golden_json(DOCUMENT)}
        return None


def document() -> Explainer:
    return Explainer.model_validate(golden_json(DOCUMENT))


def client(monkeypatch: pytest.MonkeyPatch, stored: Stored | None = None) -> tuple[TestClient, Stored]:
    kept = stored or Stored()

    async def session() -> AsyncIterator[AnswerSession]:
        yield AnswerSession(kept)

    async def resolve(session: Any, slug: str) -> Craft | None:
        return CRAFTS.get(slug)

    async def visible(
        session: Any, claim_ids: Sequence[uuid.UUID], **_kwargs: Any
    ) -> tuple[dict[uuid.UUID, None], dict[Any, Any]]:
        return dict.fromkeys(claim_ids), {}

    async def comparison(
        session: Any, crafts: Sequence[Craft], facets: Sequence[str], **_kwargs: Any
    ) -> CraftComparison | None:
        kept.asked.append(([craft.slug for craft in crafts], list(facets)))
        return None

    async def shared(session: Any, craft: Craft, **_kwargs: Any) -> SharedScience:
        kept.asked.append(craft.slug)
        return SharedScience.model_validate(learning(SHARED_SCIENCE)["craft"])

    async def concept(session: Any, term_key: str, focus: Craft | None, **_: Any) -> SharedConcept | None:
        kept.asked.append((term_key, focus.slug if focus else None))
        return (
            SharedConcept.model_validate(learning(SHARED_SCIENCE)["concept"]) if term_key == "alum" else None
        )

    monkeypatch.setattr(knowledge_view, "resolve_craft", resolve)
    monkeypatch.setattr(knowledge_view, "claims_by_id", visible)
    monkeypatch.setattr(learning_views, "craft_comparison", comparison)
    monkeypatch.setattr(learning_views, "craft_shared_science", shared)
    monkeypatch.setattr(learning_views, "shared_concept_of", concept)
    app = create_app()
    app.dependency_overrides[get_session] = session
    sign_in_as(app, lambda: READER)
    return TestClient(app), kept


def test_the_asker_gets_a_quiz_of_their_explainer(monkeypatch: pytest.MonkeyPatch) -> None:
    http, _ = client(monkeypatch)
    reply = http.get(f"/api/answers/{DOCUMENT_ID}/quiz")
    assert reply.status_code == 200 and reply.headers["cache-control"] == "private, no-cache"
    every = frozenset(c.claim_id for s in document().sections for b in s.blocks for c in b.citations())
    assert ExplainerQuiz.model_validate(reply.json()) == explainer_quiz(document(), visible_claim_ids=every)


def test_a_quiz_can_be_made_from_chosen_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    http, _ = client(monkeypatch)
    reply = http.get(f"/api/answers/{DOCUMENT_ID}/quiz", params=[("sections", "s1")])
    assert reply.status_code == 200
    ids = {o["sentence"]["text"] for q in reply.json()["quiz"]["questions"] for o in q["options"]}
    process = {s.text for b in document().sections[0].blocks for s in b.cited_sentences()}
    assert ids <= process


def test_an_explainer_with_nothing_to_quiz_answers_no_content(monkeypatch: pytest.MonkeyPatch) -> None:
    http, _ = client(monkeypatch)
    monkeypatch.setattr(answer_quiz, "explainer_quiz", lambda *_args, **_kwargs: None)
    reply = http.get(f"/api/answers/{DOCUMENT_ID}/quiz")
    assert (reply.status_code, reply.content) == (204, b"")
    assert reply.headers["cache-control"] == "private, no-cache"


@pytest.mark.parametrize("sections", [[("sections", "s9")], [("sections", "s1"), ("sections", "s1")]])
def test_a_quiz_of_sections_the_explainer_lacks_is_refused(
    monkeypatch: pytest.MonkeyPatch, sections: Any
) -> None:
    http, _ = client(monkeypatch)
    assert http.get(f"/api/answers/{DOCUMENT_ID}/quiz", params=sections).status_code == 422


def test_another_reader_s_explainer_has_no_quiz(monkeypatch: pytest.MonkeyPatch) -> None:
    http, _ = client(monkeypatch, Stored(owner=SOMEONE_ELSE))
    assert http.get(f"/api/answers/{DOCUMENT_ID}/quiz").status_code == 404
    http, _ = client(monkeypatch)
    assert http.get(f"/api/answers/{uuid.UUID(int=99)}/quiz").status_code == 404
    assert http.get("/api/answers/not-a-uuid/quiz").status_code == 422


@pytest.mark.parametrize(
    ("crafts", "status"),
    [
        (["Kutch-Ajrakh"], 422),
        (["Kutch-Ajrakh"] * 5, 422),
        (["Kutch-Ajrakh", "Old-Ajrakh"], 422),
        (["Kutch-Ajrakh", "No-Such-Craft"], 404),
        (["Kutch-Ajrakh", "Bagru-Hand-Block-Print"], 204),
    ],
)
def test_a_comparison_needs_two_to_four_known_different_crafts(
    monkeypatch: pytest.MonkeyPatch, crafts: list[str], status: int
) -> None:
    http, _ = client(monkeypatch)
    assert http.get("/api/compare", params=[("crafts", slug) for slug in crafts]).status_code == status


def test_an_unknown_craft_and_a_comparison_with_nothing_cited_answer_differently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, _ = client(monkeypatch)
    unknown = http.get("/api/compare", params=[("crafts", "Kutch-Ajrakh"), ("crafts", "No-Such-Craft")])
    assert (unknown.status_code, unknown.json()["detail"]) == (404, "No craft has that address.")
    empty = http.get(
        "/api/compare", params=[("crafts", "Kutch-Ajrakh"), ("crafts", "Bagru-Hand-Block-Print")]
    )
    assert (empty.status_code, empty.content, empty.headers["cache-control"]) == (
        204,
        b"",
        "private, no-cache",
    )


def test_a_comparison_reads_every_field_unless_some_are_chosen(monkeypatch: pytest.MonkeyPatch) -> None:
    http, kept = client(monkeypatch)
    pair = [("crafts", "Kutch-Ajrakh"), ("crafts", "Bagru-Hand-Block-Print")]
    http.get("/api/compare", params=pair)
    http.get("/api/compare", params=[*pair, ("facets", "HISTORY"), ("facets", "HISTORY")])
    assert kept.asked == [
        (["Kutch-Ajrakh", "Bagru-Hand-Block-Print"], list(DISCIPLINES)),
        (["Kutch-Ajrakh", "Bagru-Hand-Block-Print"], ["HISTORY"]),
    ]
    assert http.get("/api/compare", params=[*pair, ("facets", "ALCHEMY")]).status_code == 422


def test_the_explorer_answers_a_known_craft_and_a_shared_term(monkeypatch: pytest.MonkeyPatch) -> None:
    http, kept = client(monkeypatch)
    assert http.get("/api/crafts/Kutch-Ajrakh/shared-science").json() == learning(SHARED_SCIENCE)["craft"]
    assert http.get("/api/crafts/No-Such-Craft/shared-science").status_code == 404
    reply = http.get("/api/shared-science/alum", params={"craft": "Kutch-Ajrakh"})
    assert reply.status_code == 200 and reply.json() == learning(SHARED_SCIENCE)["concept"]
    assert http.get("/api/shared-science/indigo").status_code == 404
    assert http.get("/api/shared-science/alum", params={"craft": "No-Such-Craft"}).status_code == 404
    assert http.get("/api/shared-science/Alum!").status_code == 422
    assert kept.asked == ["Kutch-Ajrakh", ("alum", "Kutch-Ajrakh"), ("indigo", None)]
