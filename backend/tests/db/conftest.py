import os
from collections.abc import AsyncIterator

import httpx
import pytest

from app.main import app

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
