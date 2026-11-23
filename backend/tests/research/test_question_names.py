import json
from collections.abc import Mapping
from typing import Any

from app.core.errors import ExternalFailure
from app.research.question_names import AskedQuestion, screened_questions
from app.research.structured import StructuredReply
from app.services.question_names import screen_names

LONE = AskedQuestion(
    "1", "How does Ramesh boil the cloth in Bagru?", "How does Ramesh boil the cloth in Bagru?"
)
TITLED = AskedQuestion("2", "Why does Shri Mohan Lal use alum?", "Why does [name] use alum?")
LIFE = AskedQuestion("3", "Where does Sunita live now?", "Where does Sunita live now?")


def reply(*screened: Mapping[str, Any]) -> dict[str, Any]:
    return {"questions": [dict(item) for item in screened]}


def test_a_lone_first_name_the_rules_kept_is_masked_and_a_question_about_a_person_is_dropped() -> None:
    found = screened_questions(
        (LONE, TITLED, LIFE),
        reply(
            {"key": "1", "people": ["Ramesh"], "aboutAPerson": False},
            {"key": "2", "people": ["Mohan Lal"], "aboutAPerson": False},
            {"key": "3", "people": ["Sunita"], "aboutAPerson": True},
        ),
    )
    assert found == {
        "1": "How does [name] boil the cloth in Bagru?",
        "2": "Why does [name] use alum?",
        "3": None,
    }


def test_a_name_the_question_does_not_hold_drops_it_and_an_unread_reply_holds_every_question() -> None:
    invented = reply({"key": "1", "people": ["Ravi"], "aboutAPerson": False})
    assert screened_questions((LONE,), invented) == {"1": None}
    assert screened_questions((LONE, TITLED), reply({"key": "2", "people": [], "aboutAPerson": False})) == {
        "2": "Why does [name] use alum?"
    }
    assert screened_questions((LONE,), {"questions": [{"key": "1"}]}) == {}


class Screener:
    def __init__(self, people: Mapping[str, list[str]], *, failing: bool = False) -> None:
        self.people = people
        self.failing = failing
        self.asked: list[str] = []

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.asked.append(user)
        if self.failing:
            raise ExternalFailure("the model is away", service="model")
        questions = json.loads(user)["questions"]
        screened = [
            {"key": q["key"], "people": self.people.get(q["question"], []), "aboutAPerson": False}
            for q in questions
        ]
        return StructuredReply(text=json.dumps({"questions": screened}), degraded=False)


async def test_the_screen_asks_once_per_batch_and_a_failure_holds_its_questions() -> None:
    screener = Screener({LONE.asked: ["Ramesh"]})
    screened = await screen_names(screener, (LONE, TITLED))
    assert screened.screened == {
        "1": "How does [name] boil the cloth in Bagru?",
        "2": "Why does [name] use alum?",
    }
    assert screened.error is None and len(screener.asked) == 1
    away = await screen_names(Screener({}, failing=True), (LONE,))
    assert (away.screened, away.error) == ({}, "the model is away")
