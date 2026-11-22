import httpx
import pytest

from app.core.key_checks import KEY_NOT_ACCEPTED, KEY_SPENT, KeyVerdict
from app.sources.web.brave import check_key

BRAVE_KEY = "test-brave-key-not-real"


async def checked(status: int, seen: list[httpx.Request]) -> KeyVerdict:
    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json={"type": "search"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
        return await check_key(client, BRAVE_KEY)


async def test_the_key_travels_in_the_subscription_token_header_of_a_one_result_search() -> None:
    seen: list[httpx.Request] = []
    assert await checked(200, seen) == KeyVerdict(ok=True)
    (sent,) = seen
    assert (sent.url.host, sent.url.path) == ("api.search.brave.com", "/res/v1/web/search")
    assert sent.headers["x-subscription-token"] == BRAVE_KEY
    assert (sent.url.params["q"], sent.url.params["count"]) == ("kalamkari", "1")
    assert BRAVE_KEY not in str(sent.url)


@pytest.mark.parametrize(
    ("status", "verdict"),
    [
        (401, KeyVerdict(ok=False, error=KEY_NOT_ACCEPTED)),
        (403, KeyVerdict(ok=False, error=KEY_NOT_ACCEPTED)),
        (429, KeyVerdict(ok=False, error=KEY_SPENT)),
    ],
)
async def test_a_refused_or_spent_key_says_so(status: int, verdict: KeyVerdict) -> None:
    assert await checked(status, []) == verdict
