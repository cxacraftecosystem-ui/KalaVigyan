import os
from collections import Counter
from collections.abc import AsyncIterator

import httpx
import pytest

from app.main import app

from .shards import SHARD_VARIABLE, module_of, parse_shard, split_modules


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    value = os.environ.get(SHARD_VARIABLE)
    if not value:
        return
    shard = parse_shard(value)
    weights = Counter(module_of(item.nodeid) for item in items)
    chosen = set(split_modules(weights, shard.total)[shard.index - 1])
    dropped = [item for item in items if module_of(item.nodeid) not in chosen]
    items[:] = [item for item in items if module_of(item.nodeid) in chosen]
    if dropped:
        config.hook.pytest_deselected(items=dropped)


@pytest.fixture(scope="session")
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
