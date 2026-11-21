import logging
from typing import Any

import httpx
import pytest

from app.core.errors import ExternalFailure
from app.models import AuditLog
from app.services.site_build import DeployHook, deploy_hook, trigger_site_build
from app.sources.wayback_save import WaybackSaver

from .fakes import CountingHook

PAGE = "https://crafts.example.org/ajrakh/mordants?lang=en"
SNAPSHOT = f"https://web.archive.org/web/20261120003000/{PAGE}"
HOOK = "https://api.vercel.com/v1/integrations/deploy/prj_test/hook-secret-0123"


def saver(answer: httpx.Response, asked: list[str]) -> WaybackSaver:
    def handle(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return answer

    return WaybackSaver(httpx.AsyncClient(transport=httpx.MockTransport(handle)))


async def test_the_save_endpoint_redirect_names_the_snapshot() -> None:
    asked: list[str] = []
    found = await saver(httpx.Response(302, headers={"location": SNAPSHOT}), asked).save(PAGE)
    assert found == SNAPSHOT
    assert asked == [f"https://web.archive.org/save/{PAGE}"]


async def test_a_relative_content_location_becomes_the_snapshot_address() -> None:
    answer = httpx.Response(200, headers={"content-location": f"/web/20261120003000/{PAGE}"})
    assert await saver(answer, []).save(PAGE) == SNAPSHOT


@pytest.mark.parametrize(
    ("answer", "kind"),
    [
        (httpx.Response(429), "rate_limit"),
        (httpx.Response(520), "unavailable"),
        (httpx.Response(200), "error"),
    ],
)
async def test_a_save_that_names_no_snapshot_fails(answer: httpx.Response, kind: str) -> None:
    with pytest.raises(ExternalFailure) as failed:
        await saver(answer, []).save(PAGE)
    assert failed.value.kind == kind
    assert failed.value.service == "wayback-save"


def hook_client(status: int, posted: list[str]) -> httpx.AsyncClient:
    def handle(request: httpx.Request) -> httpx.Response:
        posted.append(f"{request.method} {request.url}")
        logging.getLogger("httpx").info("HTTP Request: %s %s", request.method, request.url)
        return httpx.Response(status, json={"job": {"state": "PENDING"}})

    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


async def test_the_deploy_hook_is_posted_once_and_its_address_never_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    posted: list[str] = []
    caplog.set_level(logging.INFO, logger="httpx")
    await DeployHook(HOOK, hook_client(201, posted)).trigger()
    assert posted == [f"POST {HOOK}"]
    assert all("hook-secret" not in record.getMessage() for record in caplog.records)


async def test_a_refused_deploy_hook_fails_without_naming_its_address() -> None:
    with pytest.raises(ExternalFailure) as failed:
        await DeployHook(HOOK, hook_client(404, [])).trigger()
    assert str(failed.value) == "the deploy hook answered 404"
    assert failed.value.kind == "not_found"


def test_an_unset_or_blank_hook_is_no_hook() -> None:
    client = httpx.AsyncClient()
    assert deploy_hook(None, client) is None
    assert deploy_hook("   ", client) is None
    assert isinstance(deploy_hook(HOOK, client), DeployHook)


class AuditSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.commits = 0

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.commits += 1


async def test_a_triggered_build_is_audited_with_who_asked() -> None:
    session = AuditSession()
    hook = CountingHook()
    actor = type("Admin", (), {"id": "a0000000-0000-4000-8000-000000000001"})()
    await trigger_site_build(session, hook, actor=actor, origin="admin")  # type: ignore[arg-type]
    assert hook.triggered == 1
    [entry] = session.added
    assert isinstance(entry, AuditLog)
    assert (entry.action, entry.actorKind, entry.targetType, entry.detail) == (
        "site_build.triggered",
        "USER",
        "site",
        {"origin": "admin"},
    )
    assert session.commits == 1
