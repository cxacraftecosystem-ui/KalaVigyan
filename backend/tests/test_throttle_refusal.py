import pytest
from fastapi import HTTPException

from app.core.throttle_refusal import refuse_when_throttled, too_many_requests


def test_a_refusal_waits_whole_seconds_rounded_up() -> None:
    refused = too_many_requests("Slow down.", 59.01)
    assert (refused.status_code, refused.detail, refused.headers) == (
        429,
        "Slow down.",
        {"Retry-After": "60"},
    )


def test_a_refusal_waits_at_least_one_second() -> None:
    assert too_many_requests("Slow down.", 0.2).headers == {"Retry-After": "1"}


def test_a_refusal_without_a_wait_names_none() -> None:
    assert too_many_requests("Locked.").headers is None


def test_an_allowed_attempt_passes() -> None:
    refuse_when_throttled((True, 0.0), "Slow down.")


def test_a_spent_attempt_is_refused_with_its_wait() -> None:
    with pytest.raises(HTTPException) as refused:
        refuse_when_throttled((False, 12.5), "Slow down.")
    assert (refused.value.status_code, refused.value.headers) == (429, {"Retry-After": "13"})
