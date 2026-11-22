from decimal import Decimal

import pytest

from app.core.roles import ROLE_RANK
from app.models.enums import EXPLAINER_DEPTHS
from app.providers import budget, router as ai_router
from app.providers.answer_routes import COMPOSE_TUNINGS, EXPLAINER_TUNINGS
from app.providers.catalogue import AiTask
from app.providers.router import Principal, RouteTuning

from .router_fakes import Recorded, record_router


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> Recorded:
    return record_router(monkeypatch)


def tunings_of(depth: str) -> tuple[tuple[str, RouteTuning, str], ...]:
    expert = depth == "EXPERT"
    return (
        ("compose", COMPOSE_TUNINGS[depth], "claude-opus-5-5" if expert else "claude-sonnet-5-5"),
        ("explainer", EXPLAINER_TUNINGS[depth], "claude-opus-5-5" if expert else "claude-sonnet-5-5"),
    )


@pytest.mark.parametrize("depth", EXPLAINER_DEPTHS)
@pytest.mark.parametrize("role", ROLE_RANK)
async def test_no_role_or_depth_is_refused_degraded_or_cut_short_and_every_cost_is_recorded(
    recorded: Recorded, role: str, depth: str
) -> None:
    answer = budget.AnswerSpend(depth=depth)
    asks = [Principal(role=role, answer=answer), Principal(role=role, answer=answer.headroom())]
    for (_name, tuning, model), principal in zip(tunings_of(depth), asks, strict=True):
        result = await ai_router.run(
            AiTask.COMPOSE,
            system="s",
            user="u",
            principal=principal,
            session_factory=recorded.sessions(),
            tuning=tuning,
        )
        assert (result.degraded, result.model, result.cost_usd > 0) == (False, model, True)
    assert [request.max_tokens for request in recorded.requests] == [128_000, 128_000]
    assert [(event.outcome, event.role, event.estimatedCostUsd > 0) for event in recorded.reserved] == [
        ("RESERVED", role, True),
        ("RESERVED", role, True),
    ]
    assert [(entry["outcome"], entry["output_tokens"]) for entry in recorded.settled] == [
        ("OK", 30_000),
        ("OK", 30_000),
    ]
    assert answer.spent_usd == sum((entry["cost_usd"] for entry in recorded.settled), Decimal(0))
    assert answer.held_usd == Decimal(0)


@pytest.mark.parametrize("role", ROLE_RANK)
@pytest.mark.parametrize(
    "task",
    [AiTask.PLAN, AiTask.TRANSLATE, AiTask.SUMMARISE, AiTask.VOICE_TURN, AiTask.INTERVIEW, AiTask.TESTIMONY],
)
async def test_term_summaries_translation_voice_interview_and_testimony_run_uncapped_at_the_maximum(
    recorded: Recorded, role: str, task: AiTask
) -> None:
    result = await ai_router.run(
        task, system="s", user="u", principal=Principal(role=role), session_factory=recorded.sessions()
    )
    assert (result.degraded, recorded.requests[0].max_tokens) == (False, 128_000)
    assert recorded.settled[0]["outcome"] == "OK" and recorded.settled[0]["cost_usd"] > 0
