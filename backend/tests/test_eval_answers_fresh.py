import asyncio

import pytest

from app.scripts import eval_answers
from app.services.answer_runs import AnswerRun
from app.services.answering import AnswerAsk

ASKED = AnswerAsk(
    question="Why does the cloth turn blue in the air?", depth="DETAILED", craft_slug="Kutch-Ajrakh"
)


def test_a_fresh_answer_asks_the_same_question_with_no_stored_section_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[AnswerAsk] = []

    async def answered(ask: AnswerAsk) -> AnswerRun:
        seen.append(ask)
        return AnswerRun(answer_id=None, problem="not asked")

    monkeypatch.setattr(eval_answers, "answer", answered)
    asyncio.run(eval_answers.fresh_answer(ASKED))
    assert [(ask.question, ask.depth, ask.craft_slug, ask.fresh) for ask in seen] == [
        (ASKED.question, "DETAILED", "Kutch-Ajrakh", True)
    ]
    assert ASKED.fresh is False


@pytest.mark.parametrize(("argv", "chosen"), [([], "answer"), (["--fresh"], "fresh_answer")])
def test_the_fresh_flag_chooses_the_fresh_answering(
    monkeypatch: pytest.MonkeyPatch, argv: list[str], chosen: str
) -> None:
    picked: list[object] = []

    async def run(*, answering: object, **kwargs: object) -> dict[str, int]:
        picked.append(answering)
        return {"answered": 1}

    monkeypatch.setattr(eval_answers, "run", run)
    assert eval_answers.main(argv) == 0
    assert picked == [getattr(eval_answers, chosen)]
