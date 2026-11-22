import hashlib
import hmac
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.public_deps import counted_anonymous_read
from app.core import allowances
from app.core.allowances import AllowanceUnread, Ask, Bucket, Counted
from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import get_current_user_any_step
from app.core.rate_limit import (
    ask_attempt,
    code_attempt,
    public_read_attempt,
    refund_code,
    sign_in_attempt_by_account,
)
from app.main import create_app
from app.models import User
from app.models.allowances import ALLOWANCE_HOLDER_CHARS

from .allowance_counter import MemoryCounter

MOMENT = datetime(2026, 11, 22, 10, 5, tzinfo=UTC)
WINDOW_START = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
VISITOR = "203.0.113.5"


class UnreadCounter:
    async def take(self, bucket: Bucket, ask: Ask) -> Counted:
        raise AllowanceUnread("not counted")

    async def give_back(self, bucket: Bucket) -> None:
        raise AllowanceUnread("not given back")


def visitor(address: str) -> Any:
    return SimpleNamespace(client=SimpleNamespace(host=address), headers={})


def digest(subject: str) -> str:
    key = get_settings().jwt_secret.encode("utf-8")
    return hmac.new(key, f"limit:{subject}".encode(), hashlib.sha256).hexdigest()[:32]


async def codes(user_id: str, tries: int) -> list[bool]:
    return [(await code_attempt(user_id, now=MOMENT))[0] for _ in range(tries)]


async def test_two_processes_sharing_one_store_count_against_one_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store: dict[Bucket, int] = {}
    processes = (MemoryCounter(store), MemoryCounter(store))
    answered = []
    for turn in range(31):
        monkeypatch.setattr(allowances, "counter", processes[turn % 2])
        answered.append((await ask_attempt("u", now=MOMENT))[0])
    assert answered == [True] * 30 + [False]


async def test_a_refunded_code_attempt_is_given_back_once() -> None:
    assert await codes("u", 11) == [True] * 10 + [False]
    await refund_code("u", now=MOMENT)
    assert await codes("u", 2) == [True, False]


async def test_refunds_never_count_below_nothing() -> None:
    await refund_code("u", now=MOMENT)
    assert await codes("u", 1) == [True]
    await refund_code("u", now=MOMENT)
    await refund_code("u", now=MOMENT)
    assert await codes("u", 11) == [True] * 10 + [False]


async def test_a_limit_stores_a_keyed_digest_of_the_address_never_the_address(
    allowance_counter: MemoryCounter,
) -> None:
    await public_read_attempt(visitor(VISITOR), now=MOMENT)
    assert list(allowance_counter.used) == [Bucket(digest(VISITOR), "public-read", WINDOW_START, 600)]


async def test_an_account_key_of_any_length_fits_the_holder_column(allowance_counter: MemoryCounter) -> None:
    unknown = "addr:" + "a" * 300 + "@example.org"
    assert (await sign_in_attempt_by_account(unknown, now=MOMENT))[0] is True
    (bucket,) = allowance_counter.used
    assert (bucket.kind, bucket.holder) == ("acct", digest(unknown))
    assert len(bucket.holder) <= ALLOWANCE_HOLDER_CHARS


async def test_a_count_that_cannot_be_read_refuses_for_a_minute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(allowances, "counter", UnreadCounter())
    assert await ask_attempt("u", now=MOMENT) == (False, 60.0)
    assert await public_read_attempt(visitor(VISITOR), now=MOMENT) == (False, 60.0)
    with pytest.raises(HTTPException) as refused:
        await counted_anonymous_read(visitor(VISITOR))
    assert (refused.value.status_code, refused.value.headers) == (429, {"Retry-After": "60"})
    assert await refund_code("u", now=MOMENT) is None


async def no_session() -> AsyncIterator[None]:
    yield None


def test_a_spent_code_budget_answers_429_with_a_retry_after() -> None:
    user = User(
        id=uuid.UUID(int=41), name="Asha", email="asha@example.org", role="STUDENT", twoFactorEnabled=True
    )
    app = create_app()
    app.dependency_overrides[get_current_user_any_step] = lambda: user
    app.dependency_overrides[get_session] = no_session
    client = TestClient(app)
    answers = [client.post("/api/auth/two-factor/enable", json={"code": "123456"}) for _ in range(11)]
    assert [answer.status_code for answer in answers] == [409] * 10 + [429]
    assert 91 <= int(answers[-1].headers["retry-after"]) <= 990
