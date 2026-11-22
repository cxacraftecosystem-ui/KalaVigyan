import uuid
from collections.abc import Callable
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.api.routes import knowledge
from app.models import User
from app.providers import answer_routes, budget
from app.providers.catalogue import AiTask
from app.providers.router import Principal
from app.scripts import rebuild_pieces
from app.services import answer_store
from app.services.block_builders import BlockBuilders
from app.services.builder_interface import BuilderTools

from ..test_budget import ceilings

ADMIN = User(id=uuid.UUID(int=7), name="Asha Rao", email="asha@example.org", role="ADMIN")
STATE = SimpleNamespace(craft_index=None, live_sources=None, shielded_work=None)


def from_the_route(depth: str) -> None:
    knowledge.answer_pipelines(SimpleNamespace(app=SimpleNamespace(state=STATE)), ADMIN)(depth)


def from_the_nightly_rebuild(depth: str) -> None:
    rebuild_pieces.rebuild_pipeline(depth, sessions=None, index=None, live=None, shield=None)


def asked(principal: Principal) -> budget.BudgetDecision:
    left = principal.answer.left(ceilings())
    estimate = Decimal("0.01")
    return budget.evaluate(
        ceilings(),
        budget.SpendState(),
        estimate_usd=estimate,
        is_media=False,
        role="ADMIN",
        answer_left_usd=left,
    )


@pytest.mark.parametrize("build", [from_the_route, from_the_nightly_rebuild])
def test_builders_plan_and_compose_only_from_the_answer_s_headroom(
    monkeypatch: pytest.MonkeyPatch, build: Callable[[str], None]
) -> None:
    made: list[SimpleNamespace] = []
    started: list[BuilderTools] = []

    def model(task: AiTask, principal: Principal | None = None, **_: Any) -> SimpleNamespace:
        made.append(SimpleNamespace(task=task, principal=principal))
        return made[-1]

    def from_registry(cls: type, tools: BuilderTools, *_: Any) -> BlockBuilders:
        started.append(tools)
        return BlockBuilders()

    monkeypatch.setattr(answer_routes, "router_structured_model", model)
    for module in (knowledge, rebuild_pieces):
        monkeypatch.setattr(module, "router_embedder", lambda principal: None)
    monkeypatch.setattr(knowledge, "sessionmaker", lambda: None)
    monkeypatch.setattr(answer_store.BlockBuilders, "from_registry", classmethod(from_registry))
    build("DETAILED")
    (tools,) = started
    headroom = tools.plan_model.principal.answer
    assert (tools.plan_model.task, tools.compose_model.task) == (AiTask.PLAN, AiTask.COMPOSE)
    assert isinstance(headroom, budget.AnswerHeadroom)
    assert tools.compose_model.principal.answer is headroom
    assert tools.explainer_model is not None and tools.explainer_model.principal.answer is headroom
    answering = next(m for m in made if m.task == AiTask.PLAN and m.principal.answer is headroom.answer)
    headroom.answer.settle(Decimal(0), ceilings().answer_usd["DETAILED"] / 2)
    refused = asked(tools.plan_model.principal)
    assert (refused.allowed, refused.reason) == (False, budget.ANSWER_CAP)
    assert asked(answering.principal).allowed
