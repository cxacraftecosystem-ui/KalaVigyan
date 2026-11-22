import json
import re
import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.core.errors import SPEND_REFUSAL_KIND, ExternalFailure
from app.core.logging import current_request_id
from app.providers.router import RouterError
from app.research.structured import StructuredReply
from app.retrieval.golden import GeneratedQuestion, GeneratedSet
from app.retrieval.question_generation import GenerationPlan, WritingTools, generate_questions
from app.retrieval.question_writing import CraftFacts, EvalFact

TAG = "eval-questions-test0001"
REF = re.compile(r"^(\d+)\.", re.MULTILINE)


def fact_id(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-question-generation/{name}")


def facts(prefix: str, count: int) -> tuple[EvalFact, ...]:
    return tuple(
        EvalFact(fact_id(f"{prefix}-{n}"), f"Fact number {n} about alum mordant.", "CHEMISTRY")
        for n in range(count)
    )


def craft(slug: str, sampled: tuple[EvalFact, ...]) -> CraftFacts:
    return CraftFacts(
        slug=slug, names=(slug.replace("-", " "),), second_language="hi", facts=sampled, sampled=sampled
    )


async def stream(*crafts: CraftFacts) -> AsyncIterator[CraftFacts]:
    for one in crafts:
        yield one


class Writer:
    def __init__(self, failure: Exception | None = None) -> None:
        self.sizes: list[int] = []
        self.request_ids: list[str | None] = []
        self.failure = failure

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.request_ids.append(current_request_id())
        refs = REF.findall(user)
        self.sizes.append(len(refs))
        if self.failure is not None:
            raise self.failure
        items = [
            {"ref": ref, "question": "Which salt is meant here?", "unavoidable": [], "translated": ""}
            for ref in refs
        ]
        return StructuredReply(text=json.dumps({"questions": items}), degraded=False, model="cheap-model")


def tools(writer: Writer, spent: Sequence[Decimal] = (Decimal(0),)) -> WritingTools:
    async def spend() -> Decimal:
        return spent[0]

    return WritingTools(write=writer, spent=spend, tag=TAG)


async def test_each_batch_of_at_most_twenty_five_facts_is_one_call_under_its_own_request_id() -> None:
    writer = Writer()
    sampled = facts("one", 30)
    outcome = await generate_questions(
        stream(craft("A-Craft", sampled)), tools(writer), GenerationPlan(concurrency=1)
    )
    assert sorted(writer.sizes) == [5, 25]
    assert sorted(writer.request_ids) == [f"{TAG}-b00001", f"{TAG}-b00002"]
    assert {question.key for question in outcome.questions} == {f"{fact.id}-en" for fact in sampled}
    assert (outcome.crafts, outcome.facts, outcome.batches, outcome.model) == (1, 30, 2, "cheap-model")


async def test_a_fact_sampled_for_two_crafts_is_written_once() -> None:
    writer = Writer()
    shared = facts("shared", 2)
    crafts = stream(craft("A-Craft", shared), craft("B-Craft", (*shared, *facts("own", 1))))
    outcome = await generate_questions(crafts, tools(writer), GenerationPlan())
    assert sorted(writer.sizes) == [1, 2]
    assert [question.craft_slug for question in outcome.questions].count("A-Craft") == 2
    assert outcome.facts == 3


def kept_question(fact: EvalFact, *, extra: uuid.UUID, rejected: uuid.UUID) -> GeneratedQuestion:
    return GeneratedQuestion(
        key=f"{fact.id}-en",
        craft_slug="A-Craft",
        question="Which salt was asked before?",
        expected=((str(fact.id), str(extra)),),
        field="CHEMISTRY",
        fact=fact.id,
        language="en",
        rejected=(rejected,),
    )


async def test_a_question_kept_from_the_last_set_is_reused_with_its_judged_claims() -> None:
    extra, rejected, twin = fact_id("judged-extra"), fact_id("judged-rejected"), fact_id("twin")
    first, second = facts("kept", 2)
    restated = EvalFact(first.id, first.text, first.field, restatements=(twin, rejected))
    previous = GeneratedSet(
        version=1,
        revision=3,
        generated_at=datetime(2026, 11, 1, tzinfo=UTC),
        seed=7,
        facts_per_craft=20,
        questions=(kept_question(first, extra=extra, rejected=rejected),),
    )
    writer = Writer()
    outcome = await generate_questions(
        stream(craft("A-Craft", (restated, second))), tools(writer), GenerationPlan(), previous
    )
    assert writer.sizes == [1]
    assert outcome.reused == 1
    reused = next(question for question in outcome.questions if question.fact == first.id)
    assert reused.facts == ((str(first.id), str(twin), str(extra)),)
    assert reused.rejected == (rejected,)
    built = outcome.generated(GenerationPlan(), revision=4, at=datetime(2026, 11, 22, tzinfo=UTC))
    assert built.revision == 4 and len(built.questions) == 2


async def test_a_kept_question_not_in_its_language_s_script_is_dropped_and_not_reused() -> None:
    first, second = facts("scripts", 2)
    english = kept_question(first, extra=fact_id("extra"), rejected=fact_id("refused"))
    devanagari = english.model_copy(
        update={"key": f"{first.id}-bn", "language": "bn", "question": "कौन सा नमक पहले पूछा गया था?"}
    )
    bengali = GeneratedQuestion(
        key=f"{second.id}-bn",
        craft_slug="A-Craft",
        question="কোন লবণ আগে জিজ্ঞাসা করা হয়েছিল?",
        expected=((str(second.id),),),
        field="CHEMISTRY",
        fact=second.id,
        language="bn",
    )
    previous = GeneratedSet(
        version=1,
        revision=1,
        generated_at=datetime(2026, 11, 22, tzinfo=UTC),
        seed=7,
        facts_per_craft=20,
        questions=(english, devanagari, bengali),
    )
    writer = Writer()
    outcome = await generate_questions(
        stream(craft("A-Craft", (first, second))), tools(writer), GenerationPlan(), previous
    )
    assert writer.sizes == []
    assert outcome.reused == 2
    assert sorted(question.key for question in outcome.questions) == sorted([english.key, bengali.key])
    assert outcome.dropped == {"the second-language question is not written in that language": 1}


async def test_no_batch_is_written_once_the_spend_cap_leaves_less_than_the_reserve() -> None:
    writer = Writer()
    plan = GenerationPlan(cap_usd=Decimal("1.00"))
    outcome = await generate_questions(
        stream(craft("A-Craft", facts("cap", 3))), tools(writer, [Decimal("0.96")]), plan
    )
    assert writer.sizes == []
    assert outcome.stopped == "the spend cap was reached"
    assert outcome.dropped == {"the spend cap was reached before the fact was written": 3}


async def test_a_refused_spend_stops_the_writing_and_a_failed_call_drops_only_its_batch() -> None:
    refused = Writer(RouterError(SPEND_REFUSAL_KIND, "The monthly AI budget has been reached."))
    outcome = await generate_questions(
        stream(craft("A-Craft", facts("refused", 2))), tools(refused), GenerationPlan()
    )
    assert outcome.stopped == "the spend cap was reached" and outcome.questions == []
    failing = Writer(ExternalFailure("the model is down", kind="unavailable"))
    plan = GenerationPlan(batch=1)
    outcome = await generate_questions(stream(craft("A-Craft", facts("down", 2))), tools(failing), plan)
    assert outcome.stopped is None and failing.sizes == [1, 1]
    assert outcome.dropped == {"the writer did not reply": 2}
