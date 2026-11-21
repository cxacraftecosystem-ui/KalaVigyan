import dataclasses
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

from app.api.mcp_ask_run import AskTools
from app.api.mcp_ask_tools import Ask, ask_tool
from app.api.mcp_tool_base import DATA_NOTE, ToolContext
from app.api.mcp_tools import answer
from app.core.errors import InvalidInput
from app.core.mcp_scopes import ASK_SCOPE, READ_SCOPE
from app.core.rate_limit import ask_attempt
from app.models import User
from app.research.explainer_versions import ExplainerVersionDocument
from app.research.knowledge_api import ATTRIBUTION
from app.services.answering import AnswerPipeline
from app.services.craft_resolver import CraftIndexStore
from app.services.explainer_payload import first_version_mark

from ..answering.fakes import ANSWER_ID, BOOK_ID, LAKE_ID, SOURCES, VIEWS, WEB_ID, FakeStore, pipeline
from ..answering.test_answer_components import PLAYER, FakeCatalogue, chose
from ..composer.fixtures import ALUM_CLAIM_ID, QUESTION
from ..research.fixtures import AJRAKH

SITE = "https://kalavigyan.example"
WRITTEN_LAKE = "6c1e0f2a-3b4d-4e5f-8a9b-0c1d2e3f4a5b"
WRITTEN_WASH = "8d2f1a3b-4c5e-4f60-9b1c-2d3e4f5a6b7c"
OWNER = "Meera Rao"


class FakeSession:
    def __init__(self, *, held: Any = None) -> None:
        self.held = held
        self.ended: list[str] = []

    async def commit(self) -> None:
        self.ended.append("commit")

    async def rollback(self) -> None:
        self.ended.append("rollback")

    async def scalar(self, query: Any) -> Any:
        return self.held

    async def get(self, model: Any, key: Any) -> Any:
        return None


@dataclasses.dataclass
class Asked:
    answer_pipeline: AnswerPipeline
    store: FakeStore
    runs: list[tuple[uuid.UUID, str]] = dataclasses.field(default_factory=list)

    def tools(self, timeout: float = 60.0) -> AskTools:
        @asynccontextmanager
        async def made(user: User, depth: str, index: CraftIndexStore) -> AsyncIterator[AnswerPipeline]:
            self.runs.append((user.id, depth))
            yield self.answer_pipeline

        async def stored(session: Any, answer_id: uuid.UUID, user_id: uuid.UUID) -> ExplainerVersionDocument:
            (finished,) = self.store.finished
            mark = first_version_mark(
                answer_id=answer_id, question=QUESTION, created_at="2026-11-19T10:00:00Z"
            )
            return ExplainerVersionDocument(schema_version=1, mark=mark, explainer=finished["explainer"])

        return AskTools(pipeline=made, stored=stored, timeout_seconds=timeout)


def person(role: str = "RESEARCHER", **fields: Any) -> User:
    return User(id=uuid.UUID(int=41), name=OWNER, email="meera@example.org", role=role, **fields)


def context(
    user: User | None, *, held: Any = None, scopes: frozenset[str] = frozenset({READ_SCOPE, ASK_SCOPE})
) -> ToolContext:
    return ToolContext(
        session=FakeSession(held=held), index=CraftIndexStore(), site=SITE, user=user, scopes=scopes
    )  # type: ignore[arg-type]


def answered_with_player() -> Asked:
    store = FakeStore()
    made = pipeline(replies=[chose(PLAYER.label)], store=store)
    return Asked(dataclasses.replace(made, catalogue=FakeCatalogue((PLAYER,))), store)


def sentence(text: str, level: str, claim: str, source: uuid.UUID, number: int) -> dict[str, Any]:
    return {"text": text, "level": level, "claimIds": [claim], "sourceIds": [str(source)], "cites": [number]}


async def finished() -> dict[str, Any]:
    asked = answered_with_player()
    reply = await ask_tool(asked.tools()).run(context(person()), Ask(question=QUESTION))
    return reply.model_dump(mode="json", by_alias=True)


async def test_ask_returns_the_question_its_craft_and_the_link_to_the_same_answer() -> None:
    shown = await finished()
    assert shown["schemaVersion"] == 1
    assert (shown["answerId"], shown["version"], shown["question"]) == (str(ANSWER_ID), 1, QUESTION)
    assert shown["crafts"] == [
        {"slug": "Kutch-Ajrakh", "name": "Kutch Ajrakh", "pageUrl": f"{SITE}/crafts/Kutch-Ajrakh"}
    ]
    assert (shown["depth"], shown["language"], shown["opening"]) == ("DETAILED", "en", [])
    assert shown["followUps"] == ["How is the alum bath prepared for Kutch Ajrakh?"]
    assert shown["answerUrl"] == f"{SITE}/ask?explainer={ANSWER_ID}&version=1"
    assert shown["view"] == {
        "resourceUri": "ui://kalavigyan/answer.html",
        "mimeType": "text/html;profile=mcp-app",
    }
    assert (shown["attribution"], shown["dataNote"]) == (ATTRIBUTION, DATA_NOTE)


async def test_ask_returns_each_section_with_its_cited_sentences_components_and_sources() -> None:
    shown = await finished()
    (section,) = shown["sections"]
    assert (section["id"], section["field"], section["title"]) == (
        "s1",
        "CHEMISTRY",
        "The chemistry behind Kutch Ajrakh",
    )
    assert section["sentences"] == [
        sentence(
            "Alum is the mordant that binds alizarin to cotton.", "REVIEWED", str(ALUM_CLAIM_ID), BOOK_ID, 1
        ),
        sentence(
            "Mordant baths held 8 g/L alum and were heated to 60 °C.", "PROVISIONAL", WRITTEN_LAKE, LAKE_ID, 2
        ),
        sentence("The red lake withstood 20 washes.", "PROVISIONAL", WRITTEN_WASH, WEB_ID, 3),
    ]
    assert section["components"] == [
        {
            "label": "kutch-ajrakh/chemistry/red-alum-madder-player",
            "title": "Red develops only where alum was printed",
            "kind": "reaction_player",
            "url": f"{SITE}/crafts/Kutch-Ajrakh#rp-red",
        }
    ]
    assert [(s["number"], s["id"], s["title"], s["licence"]) for s in shown["sources"]] == [
        (1, str(BOOK_ID), "Ajrakh: the printed cloth of Kutch", None),
        (2, str(LAKE_ID), "Alizarin lakes on cotton", "CC BY 4.0"),
        (3, str(WEB_ID), "Ajrakh fastness notes", None),
    ]


async def test_ask_names_each_field_it_consulted_with_its_cited_sentences_sources_and_figures() -> None:
    shown = await finished()
    (consulted,) = shown["fields"]
    assert (consulted["field"], consulted["sections"], consulted["sentences"], consulted["sources"]) == (
        "CHEMISTRY",
        1,
        3,
        3,
    )
    assert consulted["figures"] >= 1 and consulted["seats"] == []


async def test_ask_runs_the_pipeline_in_the_person_s_name_at_their_own_depth() -> None:
    asked = answered_with_player()
    user = person()
    await ask_tool(asked.tools()).run(context(user), Ask(question=QUESTION, craft_slug=AJRAKH.slug))
    assert asked.runs == [(user.id, "DETAILED")]
    ((ask, _),) = asked.store.begun
    assert (ask.question, ask.depth, ask.craft_slug, ask.any_craft) == (
        QUESTION,
        "DETAILED",
        "Kutch-Ajrakh",
        False,
    )
    assert (ask.user_id, ask.role, ask.withheld_terms, ask.reading_style) == (
        user.id,
        "RESEARCHER",
        (OWNER,),
        None,
    )


async def test_a_chosen_depth_and_language_are_passed_on() -> None:
    asked = answered_with_player()
    await ask_tool(asked.tools()).run(context(person()), Ask(question=QUESTION, depth="EXPERT"))
    assert asked.runs == [(uuid.UUID(int=41), "EXPERT")]


async def call(arguments: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "ask", "arguments": arguments},
    }
    reply = await answer(message, tool_context)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


@pytest.mark.parametrize(
    ("tool_context", "says"),
    [
        (context(None), "ask needs a signed-in connection"),
        (context(person(), scopes=frozenset({READ_SCOPE})), "ask needs the ask scope"),
    ],
)
async def test_ask_needs_a_signed_in_connection_with_the_ask_scope(
    tool_context: ToolContext, says: str
) -> None:
    result = await call({"question": QUESTION}, tool_context)
    assert result["isError"] is True and says in result["content"][0]["text"]


async def test_ask_refuses_one_craft_and_any_craft_together() -> None:
    result = await call(
        {"question": QUESTION, "craft_slug": "Kutch-Ajrakh", "any_craft": True}, context(person())
    )
    assert result["isError"] is True and "one craft or any craft" in result["content"][0]["text"]


async def test_ask_is_listed_with_its_ui_resource_and_as_a_write() -> None:
    reply = await answer({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, context(None))
    assert reply is not None
    (listed,) = [tool for tool in reply["result"]["tools"] if tool["name"] == "ask"]
    assert listed["_meta"] == {
        "kalavigyan/group": "reading",
        "ui": {"resourceUri": "ui://kalavigyan/answer.html", "visibility": ["model", "app"]},
        "ui/resourceUri": "ui://kalavigyan/answer.html",
    }
    assert listed["annotations"]["readOnlyHint"] is False
    assert {"answerUrl", "sections", "sources", "attribution", "dataNote"} <= set(
        listed["outputSchema"]["properties"]
    )


@pytest.mark.parametrize(
    ("user", "held", "says"),
    [
        (person(mustChangePassword=True, passwordHash="hash"), None, "Choose a new password to continue."),
        (person("PROFESSOR", twoFactorEnabled=False), None, "Turn on two-step verification to continue."),
        (
            person("STUDENT"),
            uuid.UUID(int=41),
            "Your teacher needs to confirm that your parent or guardian agrees",
        ),
        (person("STUDENT"), None, "Finish setting up your profile first."),
        (person("VISITOR"), None, "Your role does not allow this."),
    ],
)
async def test_the_site_s_own_guards_refuse_before_anything_is_spent(
    user: User, held: Any, says: str
) -> None:
    asked = answered_with_player()
    with pytest.raises(InvalidInput, match=says):
        await ask_tool(asked.tools()).run(context(user, held=held), Ask(question=QUESTION))
    assert asked.runs == [] and asked.store.begun == []


async def test_the_thirty_first_ask_in_ten_minutes_is_refused_and_says_when_to_ask_again() -> None:
    asked = answered_with_player()
    user = person()
    for _ in range(30):
        assert ask_attempt(str(user.id))[0]
    with pytest.raises(InvalidInput, match=r"Ask again in \d+ seconds"):
        await ask_tool(asked.tools()).run(context(user), Ask(question=QUESTION))
    assert asked.runs == []


async def test_the_master_admin_is_not_counted() -> None:
    asked = answered_with_player()
    user = person("MASTER_ADMIN", twoFactorEnabled=True)
    for _ in range(30):
        ask_attempt(str(user.id))
    reply = await ask_tool(asked.tools()).run(context(user), Ask(question=QUESTION))
    assert reply.answer_id == ANSWER_ID


async def test_a_spent_budget_answers_from_stored_findings_and_keeps_no_answer() -> None:
    store = FakeStore(stored=cited([VIEWS[0], VIEWS[3]]))
    asked = Asked(pipeline(store=store, spent=True), store)
    with pytest.raises(InvalidInput, match="no answer was kept"):
        await ask_tool(asked.tools()).run(context(person()), Ask(question=QUESTION))


async def test_research_that_finds_nothing_returns_what_was_searched() -> None:
    from app.research.retrieval import KnowledgeHits

    from ..answering.fakes import FakeResearch
    from ..composer.fixtures import pack

    empty = pack(stored=KnowledgeHits(craft_slug=AJRAKH.slug), evidence=(), documents=())
    store = FakeStore()
    asked = Asked(pipeline(research=FakeResearch(pack=empty), store=store), store)
    with pytest.raises(InvalidInput, match="Searched 0 stored claims"):
        await ask_tool(asked.tools()).run(context(person()), Ask(question=QUESTION))


async def test_an_answer_that_outlasts_the_timeout_is_refused() -> None:
    asked = answered_with_player()

    @asynccontextmanager
    async def slow(user: User, depth: str, index: CraftIndexStore) -> AsyncIterator[AnswerPipeline]:
        import asyncio

        await asyncio.sleep(1)
        yield asked.answer_pipeline

    tools = dataclasses.replace(asked.tools(), pipeline=slow, timeout_seconds=0.05)
    with pytest.raises(InvalidInput, match="not finished within 1 seconds"):
        await ask_tool(tools).run(context(person()), Ask(question=QUESTION))


def cited(views: list[Any]) -> Any:
    from app.services.answer_events import cited_claims

    return cited_claims(views, SOURCES)
