import threading
import time
from collections.abc import Callable
from functools import partial
from typing import Any

import requests

__all__ = [
    "ABSENT",
    "ATTEMPTS",
    "BACKOFF_S",
    "FILE_DEADLINE_S",
    "PROBE_TIMEOUT_S",
    "RETRY_ON",
    "USER_AGENT",
    "Unreachable",
    "answered",
    "found",
    "is_remote",
    "with_retries",
    "within_deadline",
]

USER_AGENT = "kalavigyan-geo-etl/0.0.1"
ATTEMPTS = 4
BACKOFF_S = 5.0
ABSENT = (404, 410)
PROBE_TIMEOUT_S = (10, 60)
RETRY_ON = (requests.RequestException,)
FILE_DEADLINE_S = 600.0
REMOTE_SCHEMES = ("http://", "https://")


class Unreachable(RuntimeError):
    pass


def with_retries[T](call: Callable[[], T], *, retry_on: tuple[type[Exception], ...], attempts: int = ATTEMPTS) -> T:
    for attempt in range(attempts - 1):
        try:
            return call()
        except retry_on:
            time.sleep(BACKOFF_S * (attempt + 1))
    return call()


def answered(method: str, url: str) -> requests.Response:
    response = requests.request(method, url, timeout=PROBE_TIMEOUT_S, headers={"User-Agent": USER_AGENT})
    if response.status_code not in ABSENT:
        response.raise_for_status()
    return response


def is_remote(location: str) -> bool:
    return location.startswith(REMOTE_SCHEMES)


def found(url: str) -> bool:
    try:
        response = with_retries(partial(answered, "HEAD", url), retry_on=RETRY_ON)
    except requests.RequestException as error:
        raise Unreachable(f"{url} is unreachable: {error}") from error
    return response.status_code not in ABSENT


def within_deadline[T](call: Callable[[], T], *, seconds: float, what: str) -> T:
    outcome: dict[str, Any] = {}

    def work() -> None:
        try:
            outcome["value"] = call()
        except Exception as error:
            outcome["error"] = error

    worker = threading.Thread(target=work, name=f"read {what}", daemon=True)
    worker.start()
    worker.join(seconds)
    if worker.is_alive():
        raise Unreachable(f"{what} not read within {seconds:g} s")
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]
