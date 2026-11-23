import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.models.crafts import EMBEDDING_DIMENSIONS
from app.providers import router
from app.providers.answer_routes import answer_models
from app.providers.catalogue import AiTask
from app.providers.judge_routes import thrifty_judges
from app.research.candidate_gates import Candidate
from app.research.judge_ladder import JudgeLadder
from app.research.structured import StructuredReply
from app.services.write_back_gates import write_back_later_gates

from ..knowledge_writes.fakes import FakeEmbedder, FakeHeldFacts, held
from ..knowledge_writes.judge_replies import compared, verdict

VECTOR = [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)
CANDIDATE = Candidate(
    ref="c1",
    statement="Ajrakh cloth is dipped in the indigo vat four times before it is washed.",
    field="PROCESS",
)
NEAR = held("near", "Ajrakh cloth goes into the indigo vat several times.", 0.86)
FAR = held("far", "Kharad weavers of Kutch spin camel wool on a hand wheel.", 0.41)
DISTINCT = {"comparisons": [compared("c1", NEAR.id, "DISTINCT", "A count is not 'several'.")]}
UNANSWERED = {"comparisons": []}
ADDS = {"verdicts": [verdict("c1", adds=True, reason="It counts the dips.")]}
CHEAPEST = {"OPENAI": "gpt-6-luna", "GEMINI": "gemini-3.5-flash-lite", "ANTHROPIC": "claude-haiku-5-5"}


class ScriptedJudge:
    def __init__(self, model: str, *replies: Mapping[str, Any]) -> None:
        self.model = model
        self.replies = [json.dumps(reply) for reply in replies]
        self.calls = 0

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.calls += 1
        return StructuredReply(text=self.replies.pop(0), degraded=False, model=self.model)


async def gated(cheap: ScriptedJudge, strong: ScriptedJudge, nearest: Sequence[Any]) -> list[Any]:
    later = await write_back_later_gates(
        FakeHeldFacts(nearest=nearest),
        [CANDIDATE],
        embed=FakeEmbedder(VECTOR),
        judge=JudgeLadder(cheap, (strong,)),
    )
    return [(outcome.gate, outcome.passed, outcome.model) for outcome in later["c1"].outcomes]


async def test_the_cheap_judge_decides_a_clear_case_alone() -> None:
    cheap, strong = ScriptedJudge("cheap-model", DISTINCT, ADDS), ScriptedJudge("strong-model")
    assert await gated(cheap, strong, [NEAR]) == [
        ("DUPLICATE", True, "cheap-model"),
        ("NOVELTY", True, "cheap-model"),
    ]
    assert (cheap.calls, strong.calls) == (2, 0)


async def test_an_unsure_cheap_judge_hands_that_question_alone_to_the_strong_one() -> None:
    cheap = ScriptedJudge("cheap-model", UNANSWERED, ADDS)
    strong = ScriptedJudge("strong-model", DISTINCT)
    assert await gated(cheap, strong, [NEAR]) == [
        ("DUPLICATE", True, "strong-model"),
        ("NOVELTY", True, "cheap-model"),
    ]
    assert (cheap.calls, strong.calls) == (2, 1)


async def test_a_write_back_far_from_every_held_fact_asks_no_judge() -> None:
    cheap, strong = ScriptedJudge("cheap-model"), ScriptedJudge("strong-model")
    assert await gated(cheap, strong, [FAR]) == [("DUPLICATE", True, None), ("NOVELTY", True, None)]
    assert (cheap.calls, strong.calls) == (0, 0)


async def test_an_answer_judges_its_write_back_on_the_cheapest_route_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[AiTask, dict[str, str] | None]] = []

    async def run(task: AiTask, **options: Any) -> SimpleNamespace:
        tuning = options["tuning"]
        seen.append((task, dict(tuning.models) if tuning is not None else None))
        return SimpleNamespace(text="{}", degraded=False, model="m")

    monkeypatch.setattr(router, "run", run)
    principal = router.Principal(role="ADMIN")
    ladder = answer_models("DETAILED", principal=principal, optional=principal).judge
    assert ladder is not None and len(ladder.models) == 2
    for model in ladder.models:
        await model(system="s", user="u", schema={"type": "object"})
    assert seen == [(AiTask.EVAL_JUDGE, CHEAPEST), (AiTask.EVAL_JUDGE, None)]


async def test_the_coverage_job_s_judges_keep_its_day_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    budgets: list[Decimal | None] = []

    async def run(task: AiTask, **options: Any) -> SimpleNamespace:
        budgets.append(options["request_budget_usd"])
        return SimpleNamespace(text="{}", degraded=False, model="m")

    async def left() -> Decimal:
        return Decimal("1.50")

    monkeypatch.setattr(router, "run", run)
    for model in thrifty_judges(request_budget_usd=left).models:
        await model(system="s", user="u", schema={"type": "object"})
    assert budgets == [Decimal("1.50"), Decimal("1.50")]
