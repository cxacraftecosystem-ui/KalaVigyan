import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.core.db import session_scope
from app.core.security import hash_password
from app.main import app
from app.models import User
from app.services import two_factor

from .accounts import PASSWORD, bearer, code, login
from .shards import SHARD_VARIABLE, dealt, parse_shard


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    value = os.environ.get(SHARD_VARIABLE)
    if not value:
        return
    kept = dealt(items, parse_shard(value))
    kept_ids = {item.nodeid for item in kept}
    dropped = [item for item in items if item.nodeid not in kept_ids]
    items[:] = kept
    if dropped:
        config.hook.pytest_deselected(items=dropped)


@pytest.fixture(scope="session")
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture(scope="session")
async def owner(client: httpx.AsyncClient) -> dict[str, Any]:
    email = os.environ["MASTER_ADMIN_EMAIL"].lower()
    async with session_scope() as session:
        existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing is None:
            session.add(
                User(email=email, name="Owner", passwordHash=hash_password(PASSWORD), role="MASTER_ADMIN")
            )
    token = await login(client, email)
    me = (await client.get("/api/auth/me", headers=bearer(token))).json()
    assert me["twoFactorSetupRequired"] is True
    gated = await client.get("/api/secrets", headers=bearer(token))
    assert gated.status_code == 403
    assert gated.headers["x-two-factor-setup-required"] == "1"
    setup = await client.post("/api/auth/two-factor/setup", headers=bearer(token))
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    enabled = await client.post(
        "/api/auth/two-factor/enable", headers=bearer(token), json={"code": code(secret)}
    )
    assert enabled.status_code == 200, enabled.text
    assert len(enabled.json()["recovery_codes"]) == two_factor.RECOVERY_CODE_COUNT
    stale = await client.get("/api/auth/me", headers=bearer(token))
    assert stale.status_code == 401
    return {"token": enabled.json()["accessToken"], "secret": secret}
