import json
import re
import uuid
from collections.abc import AsyncIterator, Mapping
from decimal import Decimal
from typing import Any

from app.core.logging import current_request_id
from app.research.structured import StructuredReply
from app.retrieval.question_generation import GenerationPlan, WritingTools, generate_questions
from app.retrieval.question_writing import (
    COPIED,
    REWRITER_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
    Copied,
    CraftFacts,
    EvalFact,
    reused_words,
    rewriting_message,
    written_questions,
)

TAG = "eval-questions-rewrite01"
REF = re.compile(r"^(\d+)\.", re.MULTILINE)
NAMES = ("Kutch Ajrakh", "Ajrakh")


def fact_id(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-question-rewriting/{name}")


ALUM = EvalFact(fact_id("alum"), "Alum fixes madder red on the cloth.", "CHEMISTRY")
IRON = EvalFact(fact_id("iron"), "Iron turns the cloth black.", "CHEMISTRY")
FACTS = (
    ALUM,
    IRON,
    EvalFact(fact_id("indigo"), "Indigo dyes the cloth blue.", "MATERIALS"),
    EvalFact(fact_id("river"), "Kutch Ajrakh cloth is washed in the river.", "PROCESS"),
    EvalFact(fact_id("roots"), "Madder roots give the cloth its red.", "BOTANY"),
)
CRAFT = CraftFacts(slug="Kutch-Ajrakh", names=NAMES, second_language="hi", facts=FACTS, sampled=(ALUM, IRON))
COPYING = "Which salt fixes madder?"
FRESH = "Which salt keeps the red on the textile?"
DARK = "What makes the textile dark?"


def reply(questions: Mapping[str, str]) -> StructuredReply:
    items = [
        {"ref": ref, "question": text, "unavoidable": [], "translated": ""} for ref, text in questions.items()
    ]
    return StructuredReply(text=json.dumps({"questions": items}), degraded=False, model="cheap-model")


class ScriptedWriter:
    def __init__(self, *answers: Mapping[str, str]) -> None:
        self.answers = list(answers)
        self.asks: list[tuple[str, str, str | None]] = []

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.asks.append((system, user, current_request_id()))
        answer = self.answers.pop(0)
        return reply({ref: answer[ref] for ref in REF.findall(user) if ref in answer})


async def stream() -> AsyncIterator[CraftFacts]:
    yield CRAFT


def tools(writer: ScriptedWriter) -> WritingTools:
    async def spent() -> Decimal:
        return Decimal(0)

    return WritingTools(write=writer, spent=spent, tag=TAG)


def test_a_copied_question_names_the_fact_s_words_it_reused() -> None:
    written = written_questions(reply({"1": COPYING, "2": DARK}), CRAFT, (ALUM, IRON), seed=7)
    assert [question.question for question in written.questions] == [DARK]
    assert written.dropped == (COPIED,)
    assert written.copied == (Copied(ALUM, "en", ("fixes", "madder")),)
    assert reused_words(COPYING, frozenset({"alum", "fixe", "madd"})) == ("fixes", "madder")


def test_the_second_ask_carries_only_the_copied_facts_with_the_words_to_avoid() -> None:
    message = rewriting_message(CRAFT, [Copied(ALUM, "en", ("fixes", "madder"))], seed=7)
    assert "Alum fixes madder red on the cloth. [your last question reused: fixes, madder]" in message
    assert REF.findall(message) == ["1"]
    assert "Iron" not in message
    assert REWRITER_SYSTEM_PROMPT.startswith(WRITER_SYSTEM_PROMPT)


async def test_a_fact_whose_question_was_copied_is_asked_again_once_and_kept_when_reworded() -> None:
    writer = ScriptedWriter({"1": COPYING, "2": DARK}, {"1": FRESH})
    outcome = await generate_questions(stream(), tools(writer), GenerationPlan(seed=7, concurrency=1))
    assert [(system, request) for system, _, request in writer.asks] == [
        (WRITER_SYSTEM_PROMPT, f"{TAG}-b00001"),
        (REWRITER_SYSTEM_PROMPT, f"{TAG}-b00001-again"),
    ]
    assert sorted(question.question for question in outcome.questions) == [DARK, FRESH]
    summary = outcome.summary()
    assert {
        name: summary[name] for name in ("asked", "keptEnglish", "keptShare", "askedAgain", "rewritten")
    } == {
        "asked": 2,
        "keptEnglish": 2,
        "keptShare": 1.0,
        "askedAgain": 1,
        "rewritten": 1,
    }
    assert outcome.dropped == {}


async def test_a_question_copied_twice_is_dropped_as_copied() -> None:
    writer = ScriptedWriter({"1": COPYING, "2": DARK}, {"1": COPYING})
    outcome = await generate_questions(stream(), tools(writer), GenerationPlan(seed=7, concurrency=1))
    assert len(writer.asks) == 2
    assert [question.question for question in outcome.questions] == [DARK]
    assert (outcome.retried, outcome.rewritten, outcome.kept_share) == (1, 0, 0.5)
    assert outcome.dropped == {COPIED: 1}
