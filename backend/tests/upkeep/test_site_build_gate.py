from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.core.errors import ExternalFailure
from app.services.web_build_gate import ApiNotLive, GitHubCommits, refuse_ahead_of_api

LIVE = "1ab422fe" + "0" * 32
LATER_API = "45ce9a17" + "1" * 32
RUNS = "/repos/cxacraftecosystem-ui/KalaVigyan/actions/workflows/backend-checks.yml/runs"


def github(answer: Callable[[httpx.Request], httpx.Response], sent: list[httpx.Request]) -> GitHubCommits:
    def recorded(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return answer(request)

    return GitHubCommits(httpx.AsyncClient(transport=httpx.MockTransport(recorded)))


def runs_then(status: str, head: str = LATER_API) -> Callable[[httpx.Request], httpx.Response]:
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path == RUNS:
            return httpx.Response(200, json={"total_count": 812, "workflow_runs": [{"head_sha": head}]})
        return httpx.Response(200, json={"status": status, "ahead_by": 1, "behind_by": 0, "files": []})

    return answer


async def test_the_newest_backend_checks_run_on_a_main_push_names_the_api_main_needs() -> None:
    sent: list[httpx.Request] = []
    assert await github(runs_then("ahead"), sent).last_api_commit() == LATER_API
    (request,) = sent
    assert (request.method, request.url.host, request.url.path) == ("GET", "api.github.com", RUNS)
    assert dict(request.url.params) == {"branch": "main", "event": "push", "per_page": "1"}
    assert request.headers["accept"] == "application/vnd.github+json"
    assert "authorization" not in request.headers


async def test_the_comparison_asks_whether_the_live_release_holds_that_commit() -> None:
    sent: list[httpx.Request] = []
    assert await github(runs_then("ahead"), sent).includes(LIVE, LATER_API) is True
    assert sent[0].url.path == f"/repos/cxacraftecosystem-ui/KalaVigyan/compare/{LATER_API}...{LIVE}"
    assert await github(runs_then("identical"), []).includes(LIVE, LATER_API) is True
    assert await github(runs_then("behind"), []).includes(LIVE, LATER_API) is False
    assert await github(runs_then("diverged"), []).includes(LIVE, LATER_API) is False


async def test_a_build_waits_while_main_changes_the_api_since_the_live_release() -> None:
    with pytest.raises(ApiNotLive) as ahead:
        await refuse_ahead_of_api(github(runs_then("behind"), []), release=LIVE)
    assert "1ab422fe0000" in ahead.value.message and ahead.value.reason == "api_not_live"


async def test_a_build_starts_when_the_live_release_is_or_holds_the_last_api_change() -> None:
    sent: list[httpx.Request] = []
    await refuse_ahead_of_api(github(runs_then("behind", head=LIVE), sent), release=LIVE)
    assert [request.url.path for request in sent] == [RUNS]
    await refuse_ahead_of_api(github(runs_then("ahead"), []), release=LIVE)


@pytest.mark.parametrize(
    ("release", "runs"),
    [("dev", [{"head_sha": LATER_API}]), (LIVE, [])],
    ids=["an API that names no release", "no Backend checks run on main"],
)
async def test_a_build_is_refused_when_the_api_main_needs_cannot_be_named(
    release: str, runs: list[Any]
) -> None:
    sent: list[httpx.Request] = []
    commits = github(lambda _: httpx.Response(200, json={"total_count": 0, "workflow_runs": runs}), sent)
    with pytest.raises(ApiNotLive):
        await refuse_ahead_of_api(commits, release=release)
    assert len(sent) == (0 if release == "dev" else 1)


@pytest.mark.parametrize(
    ("answer", "kind"),
    [
        (httpx.Response(403, json={"message": "API rate limit exceeded"}), "auth"),
        (httpx.Response(200, json={"workflow_runs": [{"head_sha": "main"}]}), "error"),
        (httpx.Response(200, text="<html>"), "error"),
    ],
    ids=["rate limited", "a run without its commit", "not JSON"],
)
async def test_github_failing_or_off_its_shape_is_a_github_failure(answer: httpx.Response, kind: str) -> None:
    with pytest.raises(ExternalFailure) as failure:
        await refuse_ahead_of_api(github(lambda _: answer, []), release=LIVE)
    assert (failure.value.service, failure.value.kind) == ("github", kind)
