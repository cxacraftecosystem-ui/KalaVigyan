import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.core.db import session_scope
from app.models import AccessRoster, QuotaPolicy, User

from .accounts import bearer, create_user, login, unique_email

pytestmark = pytest.mark.db

ADMIN_TIER = ("ADMIN", "MASTER_ADMIN")
ADMIN_ONLY_CAPABILITIES = {
    "INVITE_PROFESSORS",
    "CHANGE_ROLES",
    "DISABLE_USERS",
    "VIEW_USAGE",
    "VIEW_AUDIT_LOG",
    "MANAGE_DATASETS",
}
MASTER_ONLY_CAPABILITIES = {"MANAGE_KEYS", "MANAGE_ROUTING", "MANAGE_QUOTAS", "MANAGE_CEILINGS"}


async def signed_in(client: httpx.AsyncClient, role: str) -> str:
    email = unique_email(role.lower().replace("_", "-"))
    secret = await create_user(email, role, with_two_factor=True)
    return await login(client, email, secret)


async def account_id(email: str) -> str:
    async with session_scope() as session:
        return str((await session.execute(select(User.id).where(User.email == email))).scalar_one())


async def account(email: str) -> User:
    async with session_scope() as session:
        return (await session.execute(select(User).where(User.email == email))).scalar_one()


async def roster_entry(status: str, role: str) -> str:
    async with session_scope() as session:
        row = AccessRoster(email=unique_email("entry"), status=status, admitRole=role)
        session.add(row)
        await session.flush()
        return str(row.id)


async def roster_id(email: str) -> str:
    async with session_scope() as session:
        found = await session.execute(select(AccessRoster.id).where(AccessRoster.email == email))
        return str(found.scalar_one())


async def entry(row_id: str) -> AccessRoster:
    async with session_scope() as session:
        row = await session.get(AccessRoster, uuid.UUID(row_id))
        assert row is not None
        return row


async def send(
    client: httpx.AsyncClient, token: str, method: str, path: str, body: dict[str, Any] | None = None
) -> httpx.Response:
    return await client.request(method, path, headers=bearer(token), json=body)


async def test_admin_must_turn_on_two_step(client: httpx.AsyncClient) -> None:
    email = unique_email("admin-without-two-step")
    await create_user(email, "ADMIN")
    token = await login(client, email)
    me = (await client.get("/api/auth/me", headers=bearer(token))).json()
    assert me["role"] == "ADMIN"
    assert me["roleLabel"] == "Admin"
    assert me["twoFactorRequired"] is True
    assert me["twoFactorSetupRequired"] is True
    gated = await client.get("/api/users", headers=bearer(token))
    assert gated.status_code == 403
    assert gated.headers["x-two-factor-setup-required"] == "1"


async def test_admin_reaches_its_areas_and_no_others(client: httpx.AsyncClient) -> None:
    token = await signed_in(client, "ADMIN")
    me = (await client.get("/api/auth/me", headers=bearer(token))).json()
    capabilities = set(me["capabilities"])
    assert capabilities >= ADMIN_ONLY_CAPABILITIES
    assert not capabilities & MASTER_ONLY_CAPABILITIES
    expected = {
        "/api/usage/summary": 200,
        "/api/usage/report": 200,
        "/api/users": 200,
        "/api/access/roster": 200,
        "/api/secrets": 403,
        "/api/settings/ai-routing": 403,
        "/api/settings/ai-catalogue": 403,
        "/api/settings/ai-budget": 403,
    }
    for path, status_code in expected.items():
        assert (await client.get(path, headers=bearer(token))).status_code == status_code, path
    roster = (await client.get("/api/access/roster", headers=bearer(token))).json()
    assert roster["assignableRoles"] == ["PROFESSOR", "RESEARCHER", "ARTISAN", "STUDENT"]


async def test_admin_assigns_roles_up_to_professor(client: httpx.AsyncClient) -> None:
    token = await signed_in(client, "ADMIN")
    student = unique_email("student")
    await create_user(student, "STUDENT")
    target = await account_id(student)
    for role in ADMIN_TIER:
        refused = await send(client, token, "PATCH", f"/api/users/{target}", {"role": role})
        assert refused.status_code == 403, refused.text
        added = await send(
            client, token, "POST", "/api/access/roster", {"email": unique_email("x"), "role": role}
        )
        assert added.status_code == 403, added.text
    assert (await account(student)).role == "STUDENT"
    promoted = await send(client, token, "PATCH", f"/api/users/{target}", {"role": "PROFESSOR"})
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["role"] == "PROFESSOR"
    invited = await send(
        client, token, "POST", "/api/access/roster", {"email": unique_email("invited"), "role": "PROFESSOR"}
    )
    assert invited.status_code == 201, invited.text
    assert invited.json()["admitRole"] == "PROFESSOR"


async def test_admin_manages_a_professor(client: httpx.AsyncClient) -> None:
    token = await signed_in(client, "ADMIN")
    professor = unique_email("professor")
    await create_user(professor, "PROFESSOR", with_two_factor=True)
    target = await account_id(professor)
    renamed = await send(client, token, "PATCH", f"/api/users/{target}", {"name": "Renamed Professor"})
    assert renamed.status_code == 200, renamed.text
    reset = await send(client, token, "DELETE", f"/api/users/{target}/two-factor")
    assert reset.status_code == 200, reset.text
    assert reset.json()["twoFactorEnabled"] is False
    suspended = await send(client, token, "POST", f"/api/users/{target}/suspend")
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["accessStatus"] == "SUSPENDED"
    restored = await send(client, token, "POST", f"/api/users/{target}/restore")
    assert restored.status_code == 200, restored.text
    assert restored.json()["accessStatus"] == "ACTIVE"
    demoted = await send(client, token, "PATCH", f"/api/users/{target}", {"role": "RESEARCHER"})
    assert demoted.status_code == 200, demoted.text
    assert demoted.json()["role"] == "RESEARCHER"


@pytest.mark.parametrize("role", ADMIN_TIER)
async def test_admin_cannot_change_an_admin_tier_account(client: httpx.AsyncClient, role: str) -> None:
    token = await signed_in(client, "ADMIN")
    email = unique_email("protected")
    await create_user(email, role, with_two_factor=True)
    target = await account_id(email)
    attempts = (
        ("PATCH", f"/api/users/{target}", {"name": "Changed"}),
        ("PATCH", f"/api/users/{target}", {"role": "STUDENT"}),
        ("POST", f"/api/users/{target}/suspend", None),
        ("POST", f"/api/users/{target}/restore", None),
        ("POST", f"/api/users/{target}/sign-out-everywhere", None),
        ("DELETE", f"/api/users/{target}/two-factor", None),
        ("DELETE", f"/api/users/{target}", None),
    )
    for method, path, body in attempts:
        response = await send(client, token, method, path, body)
        assert response.status_code == 403, (method, path, response.text)
    unchanged = await account(email)
    assert (unchanged.role, unchanged.name, unchanged.deletedAt) == (role, email.split("@")[0], None)
    assert unchanged.twoFactorEnabled is True


@pytest.mark.parametrize("role", ADMIN_TIER)
async def test_admin_cannot_change_an_admin_tier_roster_entry(client: httpx.AsyncClient, role: str) -> None:
    token = await signed_in(client, "ADMIN")
    row_id = await roster_entry("ACTIVE", role)
    attempts = (
        ("PATCH", f"/api/access/roster/{row_id}", {"notes": "changed"}),
        ("PATCH", f"/api/access/roster/{row_id}", {"role": "STUDENT"}),
        ("DELETE", f"/api/access/roster/{row_id}", None),
        ("POST", f"/api/access/roster/{row_id}/decision", {"decision": "REJECT"}),
        ("POST", f"/api/access/roster/{row_id}/decision", {"decision": "APPROVE"}),
        ("POST", f"/api/access/roster/{row_id}/decision", {"decision": "APPROVE", "role": "STUDENT"}),
    )
    for method, path, body in attempts:
        response = await send(client, token, method, path, body)
        assert response.status_code == 403, (method, path, response.text)
    row = await entry(row_id)
    assert (row.status, row.admitRole, row.notes) == ("ACTIVE", role, None)


async def test_admin_restores_a_barred_professor_entry(client: httpx.AsyncClient) -> None:
    token = await signed_in(client, "ADMIN")
    row_id = await roster_entry("SUSPENDED", "PROFESSOR")
    restored = await send(
        client, token, "POST", f"/api/access/roster/{row_id}/decision", {"decision": "APPROVE"}
    )
    assert restored.status_code == 200, restored.text
    assert (await entry(row_id)).status == "ACTIVE"


async def test_the_roster_offers_each_row_only_what_its_account_lets_the_viewer_do(
    client: httpx.AsyncClient,
) -> None:
    token = await signed_in(client, "ADMIN")
    tag = uuid.uuid4().hex[:10]
    promoted, peer = f"offers-{tag}-promoted@example.com", f"offers-{tag}-professor@example.com"
    await create_user(promoted, "ADMIN", rostered=False)
    await create_user(peer, "PROFESSOR")
    async with session_scope() as session:
        session.add(AccessRoster(email=promoted, status="ACTIVE", admitRole="PROFESSOR"))
    listed = await send(client, token, "GET", f"/api/access/roster?search=offers-{tag}")
    assert listed.status_code == 200, listed.text
    offers = {item["email"]: item["offers"] for item in listed.json()["items"]}
    assert offers == {
        promoted: {"update": False, "suspend": False, "admit": False, "refuse": False},
        peer: {"update": True, "suspend": True, "admit": False, "refuse": False},
    }
    rows = {email: await roster_id(email) for email in offers}
    refused = await send(client, token, "PATCH", f"/api/access/roster/{rows[promoted]}", {"notes": "x"})
    assert refused.status_code == 403, refused.text
    corrected = await send(client, token, "PATCH", f"/api/access/roster/{rows[peer]}", {"notes": "x"})
    assert corrected.status_code == 200, corrected.text


async def test_master_admin_assigns_admin(client: httpx.AsyncClient) -> None:
    token = await signed_in(client, "MASTER_ADMIN")
    roster = (await client.get("/api/access/roster", headers=bearer(token))).json()
    assert roster["assignableRoles"] == [
        "MASTER_ADMIN",
        "ADMIN",
        "PROFESSOR",
        "RESEARCHER",
        "ARTISAN",
        "STUDENT",
    ]
    student = unique_email("future-admin")
    await create_user(student, "STUDENT")
    promoted = await send(
        client, token, "PATCH", f"/api/users/{await account_id(student)}", {"role": "ADMIN"}
    )
    assert promoted.status_code == 200, promoted.text
    assert (promoted.json()["role"], promoted.json()["roleLabel"]) == ("ADMIN", "Admin")
    assert promoted.json()["twoFactorSetupRequired"] is True
    added = await send(
        client, token, "POST", "/api/access/roster", {"email": unique_email("admin"), "role": "ADMIN"}
    )
    assert added.status_code == 201, added.text
    assert added.json()["admitRole"] == "ADMIN"


async def test_sorting_users_by_role_follows_the_rank_not_the_stored_order(client: httpx.AsyncClient) -> None:
    token = await signed_in(client, "ADMIN")
    tag = uuid.uuid4().hex[:10]
    for role in ("STUDENT", "ADMIN", "ARTISAN", "PROFESSOR", "RESEARCHER"):
        await create_user(f"rank-{tag}-{role.lower()}@example.com", role)
    ranked = ["ADMIN", "PROFESSOR", "RESEARCHER", "ARTISAN", "STUDENT"]
    for direction, expected in (("desc", ranked), ("asc", ranked[::-1])):
        listed = await client.get(
            "/api/users",
            params={"search": f"rank-{tag}", "sort": "role", "dir": direction},
            headers=bearer(token),
        )
        assert listed.status_code == 200, listed.text
        assert [item["role"] for item in listed.json()["items"]] == expected, direction


async def test_admin_allowances_and_daily_cap_are_unlimited_for_now(client: httpx.AsyncClient) -> None:
    token = await signed_in(client, "ADMIN")
    mine = (await client.get("/api/usage/me", headers=bearer(token))).json()
    assert mine["allowances"] == {"VOICE_SECONDS": None, "IMAGE": None, "VIDEO": None}
    assert (mine["dailyCapUsd"], mine["platformDegraded"]) == (None, False)
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(QuotaPolicy.resource, QuotaPolicy.perDay, QuotaPolicy.perMonth).where(
                    QuotaPolicy.role == "ADMIN"
                )
            )
        ).all()
    assert {resource: (per_day, per_month) for resource, per_day, per_month in rows} == {
        "VOICE_SECONDS": (None, None),
        "IMAGE": (None, None),
        "VIDEO": (None, None),
    }
