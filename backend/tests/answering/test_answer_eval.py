import json
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.core.errors import ExternalFailure
from app.core.logging import current_request_id
from app.research.coverage_eval import EvalQuestion
from app.research.explainer import Explainer
from app.research.structured import StructuredReply
from app.services.answer_runs import AnswerRun
from app.services.answering import AnswerAsk
from app.services.coverage_eval import EVAL_SPEND_CAP_USD, EvalTools, load_questions, run_answer_eval

from ..contracts.explainer_golden import DOCUMENT, golden_json

STARTED = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
ANSWER_COST = Decimal("3.00")
JUDGE_COST = Decimal("0.10")
SCORES = {"fields": 4, "cited": 4, "everyCited": 5, "figures": 3, "noGaps": 5, "notes": "History is thin."}


def question(n: int) -> EvalQuestion:
    return EvalQuestion(
        id=f"q-{n}",
        question=f"How is Kutch Ajrakh made, question {n}?",
        craft_slug="Kutch-Ajrakh",
        fields=["PROCESS", "GEOGRAPHY", "CHEMISTRY", "HISTORY"],
    )


class Box:
    def __init__(self, *, failing: set[str] | None = None, judge_fails: bool = False) -> None:
        self.spend: dict[str, Decimal] = defaultdict(Decimal)
        self.asked: list[tuple[str, str | None]] = []
        self.failing = failing or set()
        self.judge_fails = judge_fails

    def charge(self, amount: Decimal) -> None:
        self.spend[str(current_request_id())] += amount

    async def answer(self, ask: AnswerAsk) -> AnswerRun:
        self.asked.append((ask.question, ask.craft_slug))
        self.charge(ANSWER_COST)
        if ask.question in self.failing:
            raise RuntimeError("the answer pipeline broke")
        return AnswerRun(answer_id=uuid.uuid4(), problem=None)

    async def explainer(self, answer_id: uuid.UUID) -> Explainer | None:
        return Explainer.model_validate(golden_json(DOCUMENT))

    async def judge(self, *, system: str, user: str, schema: Any) -> StructuredReply:
        self.charge(JUDGE_COST)
        if self.judge_fails:
            raise ExternalFailure("judge route unavailable", kind="unavailable", service="judge")
        return StructuredReply(text=json.dumps(SCORES), degraded=False)

    async def spent(self, prefix: str, since: datetime) -> Decimal:
        return sum((amount for tag, amount in self.spend.items() if tag.startswith(prefix)), Decimal(0))

    def tools(self) -> EvalTools:
        return EvalTools(answer=self.answer, explainer=self.explainer, judge=self.judge, spent=self.spent)


async def test_each_question_is_answered_measured_judged_and_costed_under_its_own_tag() -> None:
    box = Box()
    report = await run_answer_eval(
        [question(1), question(2)], box.tools(), started_at=STARTED, cap_usd=Decimal(30)
    )
    assert (report.asked, report.answered, report.stopped, report.spent_usd) == (2, 2, None, "6.2000")
    first = report.questions[0]
    assert (first.id, first.spent_usd, first.problem) == ("q-1", "3.1000", None)
    assert first.measures is not None and first.measures.missed == ["HISTORY"]
    assert first.rubric == report.rubric_mean == 0.9
    assert first.judge_share == report.judge_mean == 0.84
    assert box.asked[0] == ("How is Kutch Ajrakh made, question 1?", "Kutch-Ajrakh")
    assert len(set(box.spend)) == 2 and all(tag.startswith("answer-eval-") for tag in box.spend)


async def test_the_run_stops_before_a_question_the_cap_could_not_cover_and_never_exceeds_the_constant() -> (
    None
):
    box = Box()
    report = await run_answer_eval(
        [question(1), question(2)], box.tools(), started_at=STARTED, cap_usd=Decimal(5)
    )
    assert (report.asked, report.stopped, report.cap_usd) == (1, "the spend cap was reached", "5")
    raised = await run_answer_eval([], Box().tools(), started_at=STARTED, cap_usd=Decimal(1000))
    assert raised.cap_usd == str(EVAL_SPEND_CAP_USD)


async def test_a_broken_answer_or_a_failed_judge_is_recorded_and_the_run_goes_on() -> None:
    box = Box(failing={"How is Kutch Ajrakh made, question 1?"})
    report = await run_answer_eval(
        [question(1), question(2)], box.tools(), started_at=STARTED, cap_usd=Decimal(30)
    )
    broken, kept = report.questions
    assert broken.problem == "RuntimeError: the answer pipeline broke" and broken.rubric is None
    assert kept.rubric == 0.9
    judged = await run_answer_eval(
        [question(3)], Box(judge_fails=True).tools(), started_at=STARTED, cap_usd=Decimal(30)
    )
    (only,) = judged.questions
    assert only.rubric == 0.9 and only.judge is None
    assert only.problem is not None and only.problem.startswith("the judge did not score it")


def test_the_shipped_question_set_loads_and_validates() -> None:
    questions = load_questions().questions
    assert len({question.id for question in questions}) == len(questions)
    assert all(question.depth == "DETAILED" for question in questions)
