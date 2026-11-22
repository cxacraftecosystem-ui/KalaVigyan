import uuid
from typing import Any

from app.core.errors import AppError
from app.research.stream import parse_event
from app.services.answer_quiz import with_quiz_offer

OFFERED = uuid.UUID(int=1)
WITHOUT = uuid.UUID(int=2)


class Recorder:
    def __init__(self) -> None:
        self.sent: list[tuple[str, Any]] = []

    async def emit(self, name: str, data: Any) -> None:
        self.sent.append((name, data))


async def test_a_finished_answer_says_whether_check_yourself_has_a_quiz() -> None:
    recorder = Recorder()
    asked: list[uuid.UUID] = []

    async def offers(answer_id: uuid.UUID) -> bool:
        asked.append(answer_id)
        return answer_id == OFFERED

    marked = with_quiz_offer(recorder.emit, offers)
    await marked("status", {"step": "COMPOSING", "message": "Writing"})
    await marked("done", {"answerId": str(OFFERED)})
    await marked("done", {"answerId": str(WITHOUT)})
    await marked("done", {"answerId": None})
    assert recorder.sent == [
        ("status", {"step": "COMPOSING", "message": "Writing"}),
        ("done", {"answerId": str(OFFERED), "quizAvailable": True}),
        ("done", {"answerId": str(WITHOUT), "quizAvailable": False}),
        ("done", {"answerId": None}),
    ]
    assert asked == [OFFERED, WITHOUT]
    for name, data in recorder.sent:
        parse_event(name, data)


async def test_an_offer_that_cannot_be_read_leaves_the_flag_out_and_the_answer_still_finishes() -> None:
    recorder = Recorder()

    async def unreadable(_answer_id: uuid.UUID) -> bool:
        raise AppError("the answer store is away")

    await with_quiz_offer(recorder.emit, unreadable)("done", {"answerId": str(OFFERED)})
    assert recorder.sent == [("done", {"answerId": str(OFFERED)})]
