import httpx
import pytest

from app.core.key_checks import KEY_NOT_ACCEPTED, KeyCheck, KeyVerdict
from app.sources.scholarly import core_works, elsevier, openalex, semantic_scholar, springer_nature

CHECKS = [
    openalex.check_key,
    semantic_scholar.check_key,
    core_works.check_key,
    springer_nature.check_key,
    elsevier.check_key,
]


def answering(status: int, seen: list[httpx.Request]) -> httpx.AsyncClient:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json={})

    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


async def checked(check: KeyCheck, status: int, key: str) -> tuple[KeyVerdict, httpx.Request]:
    seen: list[httpx.Request] = []
    async with answering(status, seen) as client:
        verdict = await check(client, key)
    return verdict, seen[0]


@pytest.mark.parametrize("check", CHECKS)
@pytest.mark.parametrize(
    ("status", "verdict"),
    [(200, KeyVerdict(ok=True)), (401, KeyVerdict(ok=False, error=KEY_NOT_ACCEPTED))],
)
async def test_a_scholarly_key_check_reads_the_service_s_answer(
    check: KeyCheck, status: int, verdict: KeyVerdict
) -> None:
    assert (await checked(check, status, "test-key"))[0] == verdict


async def test_openalex_takes_its_key_as_the_api_key_parameter_of_a_one_work_list() -> None:
    _, sent = await checked(openalex.check_key, 200, "oa-key")
    assert (sent.url.host, sent.url.path) == ("api.openalex.org", "/works")
    assert dict(sent.url.params) == {"per-page": "1", "api_key": "oa-key"}


async def test_semantic_scholar_takes_its_key_in_the_x_api_key_header() -> None:
    _, sent = await checked(semantic_scholar.check_key, 200, "s2-key")
    assert (sent.url.host, sent.url.path) == ("api.semanticscholar.org", "/graph/v1/paper/search")
    assert sent.headers["x-api-key"] == "s2-key"
    assert "s2-key" not in str(sent.url)


async def test_core_takes_its_key_as_a_bearer_token() -> None:
    _, sent = await checked(core_works.check_key, 200, "core-key")
    assert (sent.url.host, sent.url.path) == ("api.core.ac.uk", "/v3/search/works")
    assert sent.headers["Authorization"] == "Bearer core-key"
    assert "core-key" not in str(sent.url)


async def test_springer_nature_takes_its_key_as_the_api_key_parameter_of_a_one_record_search() -> None:
    _, sent = await checked(springer_nature.check_key, 200, "sn-key")
    assert (sent.url.host, sent.url.path) == ("api.springernature.com", "/openaccess/json")
    assert dict(sent.url.params) == {"q": "dye", "p": "1", "api_key": "sn-key"}


async def test_elsevier_takes_its_key_in_the_x_els_apikey_header() -> None:
    _, sent = await checked(elsevier.check_key, 200, "els-key")
    assert (sent.url.host, sent.url.path) == ("api.elsevier.com", "/content/search/scopus")
    assert sent.headers["X-ELS-APIKey"] == "els-key"
    assert dict(sent.url.params) == {"query": "mordant", "count": "1"}
