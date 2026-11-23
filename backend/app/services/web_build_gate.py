from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Protocol

import httpx

from app.core.errors import RETRYABLE_KINDS, ExternalFailure, Refused, failure_kind

__all__ = [
    "API_WORKFLOW",
    "GATE_SERVICE",
    "REPOSITORY",
    "ApiCommits",
    "ApiNotLive",
    "GitHubCommits",
    "github_commits",
    "refuse_ahead_of_api",
]

REPOSITORY = "cxacraftecosystem-ui/KalaVigyan"
GITHUB_API = "https://api.github.com"
API_WORKFLOW = "backend-checks.yml"
MAIN = "main"
GATE_SERVICE = "github"
GATE_TIMEOUT_SECONDS = 15.0
API_NOT_LIVE = "api_not_live"
COMMIT = re.compile(r"^[0-9a-f]{40}$")
COMPARE_STATUSES = frozenset({"identical", "ahead", "behind", "diverged"})
INCLUDED = frozenset({"identical", "ahead"})
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "kalavigyan-api",
}
NO_RELEASE = "The API names no release commit, so a build could ship a site ahead of it. Deploy backend builds the site."
NO_API_RUN = (
    "GitHub lists no Backend checks run on main, so it cannot tell which API main needs. Try again later."
)
AHEAD = (
    "Main changes the API since {release}, the release the API runs. Deploy backend builds the site "
    "once that release answers."
)


class ApiNotLive(Refused):
    def __init__(self, message: str) -> None:
        super().__init__(API_NOT_LIVE, message)


class ApiCommits(Protocol):
    async def last_api_commit(self) -> str | None: ...

    async def includes(self, release: str, commit: str) -> bool: ...


class GitHubCommits:
    def __init__(
        self, client: httpx.AsyncClient, *, repository: str = REPOSITORY, base_url: str = GITHUB_API
    ):
        self._client = client
        self._repository = repository
        self._base_url = base_url

    async def last_api_commit(self) -> str | None:
        path = f"/repos/{self._repository}/actions/workflows/{API_WORKFLOW}/runs"
        body = await self._json(path, params={"branch": MAIN, "event": "push", "per_page": "1"})
        runs = body.get("workflow_runs")
        if not isinstance(runs, list):
            raise _off_shape("a workflow run list")
        if not runs:
            return None
        head = runs[0].get("head_sha") if isinstance(runs[0], dict) else None
        if not isinstance(head, str) or not COMMIT.match(head):
            raise _off_shape("a workflow run without its commit")
        return head

    async def includes(self, release: str, commit: str) -> bool:
        body = await self._json(f"/repos/{self._repository}/compare/{commit}...{release}")
        status = body.get("status")
        if status not in COMPARE_STATUSES:
            raise _off_shape(f"a comparison status {status!r}")
        return status in INCLUDED

    async def _json(self, path: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        try:
            answer = await self._client.get(
                f"{self._base_url}{path}", params=params, headers=HEADERS, timeout=GATE_TIMEOUT_SECONDS
            )
        except httpx.HTTPError:
            raise _failure("could not be reached", kind="unavailable") from None
        if answer.status_code != httpx.codes.OK:
            status = answer.status_code
            raise _failure(f"answered {status}", kind=failure_kind(status), status=status)
        try:
            body = answer.json()
        except ValueError:
            raise _off_shape("a body that is not JSON") from None
        if not isinstance(body, dict):
            raise _off_shape("a body that is not an object")
        return body


@asynccontextmanager
async def github_commits() -> AsyncIterator[ApiCommits]:
    async with httpx.AsyncClient(follow_redirects=False) as client:
        yield GitHubCommits(client)


async def refuse_ahead_of_api(commits: ApiCommits, *, release: str) -> None:
    if not COMMIT.match(release):
        raise ApiNotLive(NO_RELEASE)
    last = await commits.last_api_commit()
    if last is None:
        raise ApiNotLive(NO_API_RUN)
    if last != release and not await commits.includes(release, last):
        raise ApiNotLive(AHEAD.format(release=release[:12]))


def _failure(what: str, *, kind: str = "error", status: int | None = None) -> ExternalFailure:
    return ExternalFailure(
        f"GitHub {what}", kind=kind, retryable=kind in RETRYABLE_KINDS, status=status, service=GATE_SERVICE
    )


def _off_shape(what: str) -> ExternalFailure:
    return _failure(f"answered off its documented shape: {what}")
