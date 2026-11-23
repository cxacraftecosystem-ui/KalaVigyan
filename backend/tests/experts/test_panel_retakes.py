import itertools
import uuid
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from app.composer.expert_takes import RETAKE_SYSTEM_PROMPT, ProposedDifference
from app.providers import router
from app.providers.answer_routes import BUILDER_TUNING, answer_models
from app.providers.catalogue import AiTask
from app.providers.router import RouterError
from app.research.structured import StructuredReply
from app.research.untrusted import untrusted_block
from app.services.block_builders import BLOCK_BUILDERS, BlockBuilders
from app.services.builder_interface import BuilderTools
from app.services.expert_seat_takes import RETAKE_LEAVES_SECONDS, RETAKE_SECONDS, retake_allowed
from app.services.expert_subjects import SubjectLookup, Subjects
from app.services.expert_view_blocks import PanelClaims, difference_refusal
from app.services.expert_views import EXPERT_VIEW_WAIT_SECONDS, ExpertPanelBuilder

from ..answering.fakes import SPENT
from .fixtures import (
    BHARMALJI,
    CLIENTELE,
    CLIENTS,
    FOUR_HUNDRED,
    MIGRATION,
    SEVENTH_CENTURY,
    PanelModel,
    asked_seat,
    build_ask,
    cited,
    differ,
    panel_model,
    said,
    take,
    tools,
)

UNCITED = {"text": SEVENTH_CENTURY.text, "quotes": []}
PANEL = ("HISTORIAN", "ANTHROPOLOGIST")
GLOSSARY_TERM = uuid.UUID("7e000000-0000-4000-8000-000000000001")
OTHER_TERM = uuid.UUID("7e000000-0000-4000-8000-000000000002")


def ticking(*seconds: float) -> Callable[[], float]:
    times = itertools.chain(seconds, itertools.repeat(seconds[-1]))
    return lambda: next(times)


def failing_historian(**retakes: Any) -> PanelModel:
    return panel_model(
        [take("HISTORIAN", said(FOUR_HUNDRED), UNCITED), take("ANTHROPOLOGIST", said(CLIENTS))], **retakes
    )


def linking(*concepts: uuid.UUID) -> tuple[SubjectLookup, list[set[uuid.UUID]]]:
    asked: list[set[uuid.UUID]] = []

    async def lookup(found: Collection[uuid.UUID]) -> Subjects:
        asked.append(set(found))
        return Subjects({concept: frozenset({GLOSSARY_TERM}) for concept in concepts})

    return lookup, asked


async def test_a_failing_take_is_taken_again_once_with_its_failures_and_shown_when_it_passes() -> None:
    model = failing_historian(retakes=[take("HISTORIAN", said(FOUR_HUNDRED), said(BHARMALJI))])
    historian, anthropologist = (await ExpertPanelBuilder(tools(model)).build(build_ask(PANEL))).blocks
    assert [sentence.text for sentence in historian.take] == [FOUR_HUNDRED.text, BHARMALJI.text]
    assert [sentence.text for sentence in anthropologist.take] == [CLIENTS.text]
    (retake,) = model.retake_calls
    assert asked_seat(retake["user"]) == "HISTORIAN"
    assert "Failed sentence 0: UNCITED" in retake["user"]
    failed = (
        f"Section: HISTORIAN\nProblems: UNCITED: the sentence cites nothing\nSentence: {SEVENTH_CENTURY.text}"
    )
    assert untrusted_block("failed-0", "earlier model output", failed) in retake["user"]
    assert retake["system"] == RETAKE_SYSTEM_PROMPT


async def test_a_retake_that_still_fails_drops_the_view_after_one_try() -> None:
    model = failing_historian()
    views = (await ExpertPanelBuilder(tools(model)).build(build_ask(PANEL))).blocks
    assert [view.seat for view in views] == ["ANTHROPOLOGIST"]
    assert [asked_seat(call["user"]) for call in model.retake_calls] == ["HISTORIAN"]


async def test_a_passing_take_and_an_empty_one_are_never_taken_again() -> None:
    model = panel_model([take("HISTORIAN", said(FOUR_HUNDRED)), take("ANTHROPOLOGIST")])
    views = (await ExpertPanelBuilder(tools(model)).build(build_ask(PANEL))).blocks
    assert ([view.seat for view in views], model.retake_calls) == (["HISTORIAN"], [])


@pytest.mark.parametrize(("elapsed", "retakes"), [(50.0, 1), (51.0, 0), (60.0, 0)])
async def test_a_take_is_taken_again_only_while_the_wait_keeps_room_for_it_and_the_differences(
    elapsed: float, retakes: int
) -> None:
    model = failing_historian(retakes=[take("HISTORIAN", said(FOUR_HUNDRED))])
    builder = ExpertPanelBuilder(tools(model), clock=ticking(0.0, elapsed))
    views = (await builder.build(build_ask(PANEL))).blocks
    assert len(model.retake_calls) == retakes
    assert [view.seat for view in views] == (
        ["HISTORIAN", "ANTHROPOLOGIST"] if retakes else ["ANTHROPOLOGIST"]
    )


def test_the_retake_keeps_its_own_bound_and_the_difference_pass_its_time() -> None:
    assert (RETAKE_SECONDS, RETAKE_LEAVES_SECONDS, EXPERT_VIEW_WAIT_SECONDS) == (20.0, 20.0, 90.0)
    assert retake_allowed(40.0) and not retake_allowed(39.9)


@dataclass
class RefusedRetakes(PanelModel):
    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        if system == RETAKE_SYSTEM_PROMPT:
            self.calls.append({"system": system, "user": user, "schema": schema})
            raise RouterError("ceiling", SPENT, reason="MONTHLY_CEILING")
        return await super().__call__(system=system, user=user, schema=schema)


async def test_a_retake_the_headroom_refuses_drops_only_its_view() -> None:
    first = failing_historian()
    model = RefusedRetakes(first.views)
    views = (await ExpertPanelBuilder(tools(model)).build(build_ask(PANEL))).blocks
    assert ([view.seat for view in views], len(model.retake_calls)) == (["ANTHROPOLOGIST"], 1)


def test_one_subject_is_one_concept_or_two_concepts_one_glossary_term_links() -> None:
    linked = Subjects(
        {MIGRATION: frozenset({GLOSSARY_TERM}), CLIENTELE: frozenset({GLOSSARY_TERM, OTHER_TERM})}
    )
    apart = Subjects({MIGRATION: frozenset({GLOSSARY_TERM}), CLIENTELE: frozenset({OTHER_TERM})})
    assert linked.same(MIGRATION, CLIENTELE) and linked.same(CLIENTELE, MIGRATION)
    assert Subjects().same(MIGRATION, MIGRATION)
    assert not apart.same(MIGRATION, CLIENTELE)
    assert not linked.same(MIGRATION, None) and not Subjects().same(None, None)


def test_a_difference_across_two_linked_concepts_is_kept() -> None:
    proposal = ProposedDifference("HISTORIAN", str(FOUR_HUNDRED.id), "ANTHROPOLOGIST", str(CLIENTS.id))
    linked = PanelClaims(
        cited(), Subjects({MIGRATION: frozenset({GLOSSARY_TERM}), CLIENTELE: frozenset({GLOSSARY_TERM})})
    )
    assert difference_refusal(proposal, set(PANEL), linked) is None
    unlinked = PanelClaims(cited(), Subjects())
    assert difference_refusal(proposal, set(PANEL), unlinked) == "the statements concern different subjects"


async def test_experts_differ_on_two_concepts_one_glossary_term_names() -> None:
    lookup, asked = linking(MIGRATION, CLIENTELE)
    model = panel_model(
        [take("HISTORIAN", said(BHARMALJI)), take("ANTHROPOLOGIST", said(CLIENTS))],
        [differ("HISTORIAN", FOUR_HUNDRED, "ANTHROPOLOGIST", CLIENTS)],
    )
    built = await ExpertPanelBuilder(tools(model), subjects=lookup).build(build_ask(PANEL))
    historian, anthropologist = built.blocks
    assert (historian.differs[0].this_view.text, historian.differs[0].other_view.text) == (
        FOUR_HUNDRED.text,
        CLIENTS.text,
    )
    assert (anthropologist.differs[0].this_view.text, anthropologist.differs[0].seat) == (
        CLIENTS.text,
        "HISTORIAN",
    )
    assert asked == [{MIGRATION, CLIENTELE}]


async def test_one_view_reads_no_glossary_links() -> None:
    lookup, asked = linking(MIGRATION, CLIENTELE)
    model = panel_model([take("HISTORIAN", said(BHARMALJI))])
    built = await ExpertPanelBuilder(tools(model), subjects=lookup).build(build_ask(("HISTORIAN",)))
    assert ([view.seat for view in built.blocks], asked) == (["HISTORIAN"], [])


async def test_the_panel_builder_calls_the_builder_compose_model_on_the_answer_s_headroom(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[AiTask, Any, Any]] = []

    async def run(task: AiTask, **options: Any) -> SimpleNamespace:
        seen.append((task, options["tuning"], options["principal"]))
        return SimpleNamespace(text='{"take": []}', degraded=False, model="claude-sonnet-5-5")

    monkeypatch.setattr(router, "run", run)
    principal, optional = router.Principal(role="ADMIN"), router.Principal(role="ADMIN")
    models = answer_models("EXPERT", principal=principal, optional=optional)
    panel = BuilderTools(
        sessions=None, live=None, plan_model=models.builder_plan, compose_model=models.builder_compose
    )
    (entry,) = [entry for entry in BLOCK_BUILDERS if entry.kind == "expert_view"]
    await BlockBuilders.from_registry(panel, [entry]).added(build_ask(("HISTORIAN",)))
    assert seen and all(call == (AiTask.COMPOSE, BUILDER_TUNING, optional) for call in seen)
    assert dict(BUILDER_TUNING.models) == {"ANTHROPIC": "claude-sonnet-5-5"}
