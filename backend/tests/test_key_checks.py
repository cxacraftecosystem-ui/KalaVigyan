from collections.abc import Callable

import httpx
import pytest

from app.core.key_catalogue import MANAGED_KEYS, KeyFormat, format_problem
from app.core.key_checks import (
    KEY_NOT_ACCEPTED,
    KEY_SPENT,
    PROVIDER_TROUBLED,
    PROVIDER_UNANSWERED,
    PROVIDER_UNREACHABLE,
    KeyCheck,
    KeyVerdict,
    checked_get,
    verdict_of_status,
)
from app.providers import anthropic_p, elevenlabs_key, gemini_p, openai_p
from app.services import managed_secrets

KEY = "test-only-value-0000"


@pytest.mark.parametrize(
    ("status", "verdict"),
    [
        (200, KeyVerdict(ok=True)),
        (204, KeyVerdict(ok=True)),
        (401, KeyVerdict(ok=False, error=KEY_NOT_ACCEPTED)),
        (403, KeyVerdict(ok=False, error=KEY_NOT_ACCEPTED)),
        (429, KeyVerdict(ok=False, error=KEY_SPENT)),
        (500, KeyVerdict(ok=False, error=PROVIDER_TROUBLED)),
        (404, KeyVerdict(ok=False, error=PROVIDER_TROUBLED)),
    ],
)
def test_a_status_reads_as_the_verdict_the_settings_screen_shows(status: int, verdict: KeyVerdict) -> None:
    assert verdict_of_status(status) == verdict


async def test_a_check_that_times_out_or_cannot_connect_says_so() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    def gone(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("gone", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(slow)) as client:
        assert await checked_get(client, "https://example.org/") == KeyVerdict(
            ok=False, error=PROVIDER_UNANSWERED
        )
    async with httpx.AsyncClient(transport=httpx.MockTransport(gone)) as client:
        assert await checked_get(client, "https://example.org/") == KeyVerdict(
            ok=False, error=PROVIDER_UNREACHABLE
        )


def answering(status: int, seen: list[httpx.Request]) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json={})

    return handler


@pytest.mark.parametrize(
    ("check", "url", "header"),
    [
        (anthropic_p.check_key, "https://api.anthropic.com/v1/models", "x-api-key"),
        (
            gemini_p.check_key,
            "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1",
            "x-goog-api-key",
        ),
        (elevenlabs_key.check_key, "https://api.elevenlabs.io/v1/user", "xi-api-key"),
    ],
)
async def test_each_ai_adapter_checks_its_key_where_its_service_documents(
    check: KeyCheck, url: str, header: str
) -> None:
    seen: list[httpx.Request] = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(answering(200, seen))) as client:
        assert await check(client, KEY) == KeyVerdict(ok=True)
    async with httpx.AsyncClient(transport=httpx.MockTransport(answering(401, seen))) as client:
        assert await check(client, KEY) == KeyVerdict(ok=False, error=KEY_NOT_ACCEPTED)
    assert [str(request.url) for request in seen] == [url, url]
    assert all(request.method == "GET" and request.headers[header] == KEY for request in seen)


async def test_anthropic_names_its_api_version() -> None:
    seen: list[httpx.Request] = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(answering(200, seen))) as client:
        await anthropic_p.check_key(client, KEY)
    assert seen[0].headers["anthropic-version"] == "2023-06-01"


@pytest.mark.parametrize(
    ("base_url", "url"),
    [
        ("https://api.openai.com/v1", "https://api.openai.com/v1/models"),
        ("https://api.deepseek.com", "https://api.deepseek.com/models"),
        ("https://api.deepseek.com/", "https://api.deepseek.com/models"),
    ],
)
async def test_openai_compatible_keys_are_checked_with_a_bearer_on_the_models_list(
    base_url: str, url: str
) -> None:
    seen: list[httpx.Request] = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(answering(200, seen))) as client:
        assert await openai_p.key_check_at(base_url)(client, KEY) == KeyVerdict(ok=True)
    assert str(seen[0].url) == url
    assert seen[0].headers["authorization"] == f"Bearer {KEY}"


def test_every_key_is_checked_by_its_adapter_or_by_its_format_and_never_both() -> None:
    by_format = {key for key, spec in MANAGED_KEYS.items() if spec.format is not None}
    assert set(managed_secrets.KEY_CHECKS) == set(MANAGED_KEYS) - by_format
    assert by_format == {
        "VOYAGE_API_KEY",
        "EXA_API_KEY",
        "TAVILY_API_KEY",
        "ELSEVIER_INSTTOKEN",
        "WILEY_TDM_TOKEN",
        "DATA_GOV_IN_API_KEY",
        "GOOGLE_CLIENT_ID",
    }


GOOGLE_HINT = "This should end in .apps.googleusercontent.com."


@pytest.mark.parametrize(
    ("value", "problem"),
    [
        ("1" * 30 + ".apps.googleusercontent.com", None),
        ("1.apps.googleusercontent.com", GOOGLE_HINT),
        ("1" * 40 + ".example.com", GOOGLE_HINT),
    ],
)
def test_a_format_only_key_is_judged_by_its_length_and_ending(value: str, problem: str | None) -> None:
    google = MANAGED_KEYS["GOOGLE_CLIENT_ID"].format
    assert google is not None
    assert format_problem(google, value) == problem


def test_a_short_value_fails_a_plain_format_with_the_default_hint() -> None:
    assert format_problem(KeyFormat(16), "fifteen-chars--") == "This doesn't look like a valid value."
    assert format_problem(KeyFormat(16), "sixteen-chars---") is None


async def test_a_check_that_raises_is_reported_untested_and_never_repeats_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def exploding(client: httpx.AsyncClient, value: str) -> KeyVerdict:
        raise RuntimeError(value)

    async def echoing(client: httpx.AsyncClient, value: str) -> KeyVerdict:
        return KeyVerdict(ok=False, error=f"refused {value}")

    spec = MANAGED_KEYS["ANTHROPIC_API_KEY"]
    monkeypatch.setattr(managed_secrets, "KEY_CHECKS", {spec.key: exploding})
    assert await managed_secrets.key_verdict(spec, KEY) == KeyVerdict(
        ok=False, error=managed_secrets.UNTESTED
    )
    monkeypatch.setattr(managed_secrets, "KEY_CHECKS", {spec.key: echoing})
    assert await managed_secrets.key_verdict(spec, KEY) == KeyVerdict(ok=False, error="refused ***")
