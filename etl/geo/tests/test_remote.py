import threading

import pytest
import requests
from test_chirps import serve

from geo_etl import remote
from geo_etl.remote import with_retries

TILE = "https://tiles.test/N21E072.tif"


def outcomes(*steps):
    queue = list(steps)
    calls: list[int] = []

    def call():
        calls.append(len(calls) + 1)
        step = queue.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    return call, calls


def test_with_retries_returns_once_a_transient_error_clears(sleeps):
    call, calls = outcomes(ValueError("a"), ValueError("b"), 42)
    assert with_retries(call, retry_on=(ValueError,)) == 42
    assert calls == [1, 2, 3]
    assert sleeps == [5.0, 10.0]


def test_with_retries_raises_the_fourth_error(sleeps):
    call, calls = outcomes(*(ValueError(f"attempt {n}") for n in range(1, 6)))
    with pytest.raises(ValueError, match="attempt 4"):
        with_retries(call, retry_on=(ValueError,))
    assert calls == [1, 2, 3, 4]
    assert sleeps == [5.0, 10.0, 15.0]


def test_with_retries_lets_other_errors_through_at_once(sleeps):
    call, calls = outcomes(KeyError("not retried"), 42)
    with pytest.raises(KeyError):
        with_retries(call, retry_on=(ValueError,))
    assert calls == [1]
    assert sleeps == []


@pytest.mark.parametrize(("status", "present"), [(200, True), (404, False), (410, False)])
def test_only_404_and_410_mean_a_file_is_absent(monkeypatch, sleeps, status, present):
    server = serve(monkeypatch, {("HEAD", TILE): [status]})
    assert remote.found(TILE) is present
    assert server.calls == [("HEAD", TILE)]
    assert sleeps == []


def test_a_server_error_is_retried_then_the_file_is_unreachable_not_absent(monkeypatch, sleeps):
    server = serve(monkeypatch, {("HEAD", TILE): [503, 502, 500, 503]})
    with pytest.raises(remote.Unreachable, match=r"N21E072\.tif is unreachable: 503"):
        remote.found(TILE)
    assert server.calls == [("HEAD", TILE)] * 4
    assert sleeps == [5.0, 10.0, 15.0]


def test_a_timeout_that_clears_finds_the_file(monkeypatch, sleeps):
    stalled = requests.ReadTimeout("stalled")
    server = serve(monkeypatch, {("HEAD", TILE): [stalled, 200]})
    assert remote.found(TILE) is True
    assert server.calls == [("HEAD", TILE)] * 2
    assert sleeps == [5.0]


def test_only_http_locations_are_remote():
    assert remote.is_remote(TILE)
    assert remote.is_remote("http://tiles.test/a.tif")
    assert not remote.is_remote("/vsizip/C:/cache/glim/glim.zip/glim.asc")
    assert not remote.is_remote("C:/cache/hansen/tile.tif")


def test_a_call_within_its_deadline_returns_its_value_or_its_own_error():
    assert remote.within_deadline(lambda: 42, seconds=5.0, what="a file") == 42

    def broken():
        raise ValueError("bad block")

    with pytest.raises(ValueError, match="bad block"):
        remote.within_deadline(broken, seconds=5.0, what="a file")


def test_a_call_past_its_deadline_is_unreachable():
    released = threading.Event()
    try:
        with pytest.raises(remote.Unreachable, match="a stalled file not read within 0.05 s"):
            remote.within_deadline(lambda: released.wait(5.0), seconds=0.05, what="a stalled file")
    finally:
        released.set()


def test_the_deadline_is_the_ten_minutes_decision_0027_allowed_the_year_lookup():
    assert remote.FILE_DEADLINE_S == 600.0
