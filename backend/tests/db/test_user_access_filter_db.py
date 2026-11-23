import os
from typing import Any

import httpx
import pytest

from .accounts import bearer, create_user, unique_email

pytestmark = pytest.mark.db


async def _listed(client: httpx.AsyncClient, token: str, email: str, access: str) -> dict[str, str]:
    page = await client.get("/api/users", params={"search": email, "access": access}, headers=bearer(token))
    assert page.status_code == 200, page.text
    return {item["email"]: item["accessStatus"] for item in page.json()["items"] if item["email"] == email}


async def test_the_access_filter_finds_each_account_under_the_access_its_row_shows(
    client: httpx.AsyncClient, owner: dict[str, Any]
) -> None:
    master = os.environ["MASTER_ADMIN_EMAIL"].lower()
    unlisted = unique_email("unlisted")
    await create_user(unlisted, "STUDENT", rostered=False)
    token = owner["token"]
    assert await _listed(client, token, master, "ACTIVE") == {master: "ACTIVE"}
    assert await _listed(client, token, master, "NOT_LISTED") == {}
    assert await _listed(client, token, unlisted, "NOT_LISTED") == {unlisted: "NOT_LISTED"}
    assert await _listed(client, token, unlisted, "ACTIVE") == {}
    me = (await client.get("/api/auth/me", headers=bearer(token))).json()
    one = await client.get(f"/api/users/{me['id']}", headers=bearer(token))
    assert one.json()["accessStatus"] == "ACTIVE"
