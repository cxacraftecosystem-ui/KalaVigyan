from datetime import UTC, datetime, timedelta

import pytest

from app.services.answer_cost import answer_measures, latency_ms

ASKED = datetime(2026, 11, 22, 9, 30, tzinfo=UTC)


class UnreadSession:
    async def scalar(self, *_: object) -> object:
        raise AssertionError("no cost is read outside a request")


def test_an_answer_s_latency_is_the_milliseconds_from_its_question_to_its_finish() -> None:
    assert latency_ms(ASKED, ASKED + timedelta(seconds=285, milliseconds=412)) == 285_412
    assert latency_ms(ASKED, ASKED) == 0
    with pytest.raises(ValueError, match="before it was asked"):
        latency_ms(ASKED, ASKED - timedelta(seconds=1))


async def test_outside_a_request_an_answer_records_its_latency_and_no_cost() -> None:
    measures = await answer_measures(
        UnreadSession(), asked_at=ASKED, finished_at=ASKED + timedelta(seconds=2)
    )
    assert measures == {"latencyMs": 2000}
