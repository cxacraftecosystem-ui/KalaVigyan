import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.research.structured import StructuredReply, schema_problems
from app.retrieval.evaluation import QuestionResult, RetrievalReport
from app.retrieval.golden import GeneratedQuestion, GeneratedSet
from app.retrieval.miss_judging import (
    JudgeTools,
    MissDecision,
    judged_misses,
    miss_asks,
    miss_message,
    miss_schema,
    next_revision,
    parsed_decisions,
    texts_to_read,
    with_decisions,
)


def claim(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-miss-judging/{name}")


FACT, TWIN, OTHER, NOISE, REJECTED = (claim(name) for name in ("fact", "twin", "other", "noise", "rejected"))


def question(key: str, *, rejected: tuple[uuid.UUID, ...] = ()) -> GeneratedQuestion:
    return GeneratedQuestion(
        key=key,
        craft_slug="Kutch-Ajrakh",
        question=f"What does {key} ask?",
        expected=((str(FACT), str(TWIN)),),
        field="CHEMISTRY",
        fact=FACT,
        language="en",
        rejected=rejected,
    )


def result(key: str, ranked: tuple[uuid.UUID, ...]) -> QuestionResult:
    return QuestionResult(
        key=key, ranked=ranked, facts=({FACT: str(FACT), TWIN: str(TWIN)},), craft_slug="Kutch-Ajrakh"
    )


QUESTIONS = {
    "missed": question("missed"),
    "found": question("found"),
    "known": question("known", rejected=(REJECTED,)),
}
REPORT = RetrievalReport(
    (
        result("missed", (OTHER, NOISE, FACT)),
        result("found", (TWIN, OTHER)),
        result("known", (REJECTED, FACT)),
    )
)
TEXTS = {FACT: "Iron and tannin make the black.", OTHER: "The black comes from iron acetate on tannin."}


def test_only_a_question_whose_first_hit_is_an_unjudged_other_fact_goes_to_the_judge() -> None:
    assert texts_to_read(REPORT, QUESTIONS) == {FACT, OTHER}
    asks = miss_asks(REPORT, QUESTIONS, TEXTS)
    assert [(ask.key, ask.other, ask.expected, ask.other_text) for ask in asks] == [
        ("missed", OTHER, TEXTS[FACT], TEXTS[OTHER])
    ]
    message = miss_message(asks)
    assert "Question: What does missed ask?" in message and "Other fact: " + TEXTS[OTHER] in message
    assert schema_problems(miss_schema()) == []


def decisions_reply(*items: dict[str, Any]) -> StructuredReply:
    return StructuredReply(text=json.dumps({"decisions": list(items)}), degraded=False, model="cheap")


def test_each_ask_takes_its_first_well_formed_decision() -> None:
    asks = miss_asks(REPORT, QUESTIONS, TEXTS)
    reply = decisions_reply(
        {"ref": "1", "answers": "yes"}, {"ref": "1", "answers": True}, {"ref": "1", "answers": False}
    )
    assert parsed_decisions(reply, asks) == [MissDecision("missed", OTHER, True)]
    assert parsed_decisions(decisions_reply({"ref": "7", "answers": True}), asks) == []


def test_a_fact_the_judge_accepts_counts_as_found_and_joins_the_next_revision() -> None:
    accepted = [MissDecision("missed", OTHER, True)]
    rescored = with_decisions(REPORT, accepted)
    missed = next(one for one in rescored.results if one.key == "missed")
    assert (missed.recall, missed.reciprocal_rank) == (1.0, 1.0)
    assert REPORT.results[0].reciprocal_rank == 1 / 3
    generated = GeneratedSet(
        version=1,
        revision=2,
        generated_at=datetime(2026, 11, 22, tzinfo=UTC),
        seed=7,
        facts_per_craft=20,
        questions=tuple(QUESTIONS.values()),
    )
    revised = next_revision(generated, [*accepted, MissDecision("found", NOISE, False)])
    assert revised.revision == 3
    by_key = {one.key: one for one in revised.questions}
    assert by_key["missed"].facts == ((str(FACT), str(TWIN), str(OTHER)),)
    assert (by_key["found"].facts, by_key["found"].rejected) == (((str(FACT), str(TWIN)),), (NOISE,))
    assert next_revision(generated, []) is generated


class Judge:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.calls += 1
        return decisions_reply({"ref": "1", "answers": False})


async def test_the_judge_is_not_asked_once_the_cap_leaves_less_than_the_reserve() -> None:
    asks = miss_asks(REPORT, QUESTIONS, TEXTS)
    judge = Judge()

    async def spent() -> Decimal:
        return Decimal("0.97")

    decisions, stopped = await judged_misses(
        asks, JudgeTools(judge=judge, spent=spent, tag="eval-misses-test0001")
    )
    assert (decisions, stopped, judge.calls) == ([], "the spend cap was reached", 0)

    async def nothing() -> Decimal:
        return Decimal(0)

    decisions, stopped = await judged_misses(
        asks, JudgeTools(judge=judge, spent=nothing, tag="eval-misses-test0001")
    )
    assert (decisions, stopped, judge.calls) == ([MissDecision("missed", OTHER, False)], None, 1)
