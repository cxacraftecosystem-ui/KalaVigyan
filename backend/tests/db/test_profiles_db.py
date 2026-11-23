import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.core.db import session_scope
from app.models import (
    AdminDistrict,
    AdminState,
    ArtisanCraft,
    ArtisanProfile,
    AuditLog,
    ConsentRecord,
    Craft,
    StudentProfile,
    User,
    UserPreference,
)
from app.services import reader_profiles

from .accounts import bearer, create_user, login, unique_email

pytestmark = pytest.mark.db

STATE_LGD = 24
DISTRICT_LGD = 449


async def signed_in(client: httpx.AsyncClient, role: str) -> tuple[str, str]:
    email = unique_email(role.lower())
    secret = await create_user(email, role, with_two_factor=role in {"PROFESSOR", "ADMIN"})
    return email, await login(client, email, secret)


async def account(email: str) -> User:
    async with session_scope() as session:
        return (await session.execute(select(User).where(User.email == email))).scalar_one()


async def place_and_crafts() -> tuple[str, str, str]:
    first, second, merged = (f"Profile-Test-{uuid.uuid4().hex[:8]}" for _ in range(3))
    async with session_scope() as session:
        await session.merge(AdminState(lgd=STATE_LGD, name="Gujarat"))
        await session.merge(AdminDistrict(lgd=DISTRICT_LGD, stateLgd=STATE_LGD, name="Kachchh"))
        target = Craft(id=uuid.uuid4(), slug=first, name="Profile Test Print")
        session.add_all([target, Craft(id=uuid.uuid4(), slug=second, name="Profile Test Weave")])
        await session.flush()
        session.add(
            Craft(id=uuid.uuid4(), slug=merged, name="Old Print", status="MERGED", mergedIntoId=target.id)
        )
    return first, second, merged


def artisan_body(*slugs: str, **credit: Any) -> dict[str, Any]:
    return {
        "craftSlugs": list(slugs),
        "districtLgd": DISTRICT_LGD,
        "spokenLanguage": "gu",
        "adultConfirmed": True,
        "credit": credit or {"mode": "FIRST_NAME", "shortName": "Ismail"},
    }


async def test_a_student_saves_an_age_band_and_gender_that_only_they_see(client: httpx.AsyncClient) -> None:
    email, token = await signed_in(client, "STUDENT")
    before = await client.get("/api/profile/me", headers=bearer(token))
    assert before.status_code == 200
    assert before.json()["profileRequired"] is True
    saved = await client.put(
        "/api/profile/me/student", json={"ageBand": "18_22", "gender": "WOMAN"}, headers=bearer(token)
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["profileRequired"] is False
    assert body["student"] == {"ageBand": "18_22", "gender": "WOMAN", "guardianConsent": "NOT_NEEDED"}
    _, professor = await signed_in(client, "PROFESSOR")
    listed = await client.get("/api/users", headers=bearer(professor))
    assert listed.status_code == 200
    assert "18_22" not in listed.text and "WOMAN" not in listed.text
    async with session_scope() as session:
        user = await account(email)
        audit = (
            (await session.execute(select(AuditLog).where(AuditLog.targetId == str(user.id)))).scalars().all()
        )
    details = [row.detail for row in audit if row.action == "profile.student_updated"]
    assert details == [{"fields": ["ageBand", "gender"]}]


async def test_each_profile_is_for_its_own_role(client: httpx.AsyncClient) -> None:
    _, researcher = await signed_in(client, "RESEARCHER")
    first, _, _ = await place_and_crafts()
    student = await client.put(
        "/api/profile/me/student", json={"ageBand": "18_22", "gender": "MAN"}, headers=bearer(researcher)
    )
    artisan = await client.put(
        "/api/profile/me/artisan", json=artisan_body(first), headers=bearer(researcher)
    )
    assert (student.status_code, artisan.status_code) == (403, 403)


async def test_an_artisan_saves_crafts_in_order_following_merges(client: httpx.AsyncClient) -> None:
    email, token = await signed_in(client, "ARTISAN")
    first, second, merged = await place_and_crafts()
    saved = await client.put(
        "/api/profile/me/artisan", json=artisan_body(second, merged), headers=bearer(token)
    )
    assert saved.status_code == 200, saved.text
    artisan = saved.json()["artisan"]
    assert [craft["slug"] for craft in artisan["crafts"]] == [second, first]
    assert artisan["district"] == {
        "lgd": DISTRICT_LGD,
        "name": "Kachchh",
        "state": {"lgd": STATE_LGD, "name": "Gujarat"},
    }
    assert artisan["credit"]["preview"] == "Ismail, Profile Test Weave, Kachchh, Gujarat"
    user = await account(email)
    async with session_scope() as session:
        preference = (
            await session.execute(select(UserPreference).where(UserPreference.userId == user.id))
        ).scalar_one()
        positions = (
            (await session.execute(select(ArtisanCraft.position).where(ArtisanCraft.userId == user.id)))
            .scalars()
            .all()
        )
    assert preference.answerLanguage == "gu"
    assert sorted(positions) == [1, 2]


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"craftSlugs": ["No-Such-Craft"]}, 404),
        ({"districtLgd": 999_999}, 404),
        ({"adultConfirmed": False}, 422),
        ({"credit": {"mode": "FULL_NAME"}}, 422),
        ({"credit": {"mode": "FULL_NAME", "name": "Ismail 9876543210"}}, 422),
    ],
)
async def test_an_artisan_profile_is_refused_when_it_does_not_resolve(
    client: httpx.AsyncClient, change: dict[str, Any], status: int
) -> None:
    _, token = await signed_in(client, "ARTISAN")
    first, _, _ = await place_and_crafts()
    response = await client.put(
        "/api/profile/me/artisan", json={**artisan_body(first), **change}, headers=bearer(token)
    )
    assert response.status_code == status, response.text


async def test_a_craft_named_twice_through_a_merge_is_refused(client: httpx.AsyncClient) -> None:
    _, token = await signed_in(client, "ARTISAN")
    first, _, merged = await place_and_crafts()
    response = await client.put(
        "/api/profile/me/artisan", json=artisan_body(first, merged), headers=bearer(token)
    )
    assert response.status_code == 422


async def test_recording_consent_takes_only_the_current_notice(client: httpx.AsyncClient) -> None:
    email, token = await signed_in(client, "ARTISAN")
    notice = await client.get("/api/artisan/recording-notice?language=gu", headers=bearer(token))
    assert notice.status_code == 200
    version = notice.json()["version"]
    stale = await client.post(
        "/api/profile/me/recording-consent",
        json={"noticeVersion": "2020-01-01", "language": "gu"},
        headers=bearer(token),
    )
    given = await client.post(
        "/api/profile/me/recording-consent",
        json={"noticeVersion": version, "language": "gu"},
        headers=bearer(token),
    )
    assert (stale.status_code, given.status_code) == (409, 201)
    withdrawn = await client.delete("/api/profile/me/recording-consent", headers=bearer(token))
    assert withdrawn.status_code == 200
    assert withdrawn.json() == {"withdrawnContributions": 0, "deletedConversations": 0}
    user = await account(email)
    async with session_scope() as session:
        kept = (
            await session.execute(
                select(ConsentRecord).where(
                    ConsentRecord.userId == user.id, ConsentRecord.kind == "ARTISAN_RECORDING"
                )
            )
        ).scalar_one()
        current = await reader_profiles.recording_consent(session, user.id)
    assert (kept.noticeVersion, kept.withdrawnAt is not None, current) == (version, True, None)
    again = await client.delete("/api/profile/me/recording-consent", headers=bearer(token))
    assert again.status_code == 200


async def test_leaving_the_student_role_deletes_the_student_profile() -> None:
    email = unique_email("leaving")
    await create_user(email, "STUDENT")
    async with session_scope() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        session.add(
            StudentProfile(userId=user.id, ageBand="14_17", gender="UNSAID", completedAt=user.createdAt)
        )
    async with session_scope() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        await reader_profiles.apply_role_change(session, user, "RESEARCHER", objects=None)
        user.role = "RESEARCHER"
    async with session_scope() as session:
        assert await session.get(StudentProfile, user.id) is None


async def test_leaving_the_artisan_role_without_shown_words_deletes_the_profile() -> None:
    email = unique_email("artisan-leaving")
    await create_user(email, "ARTISAN")
    first, _, _ = await place_and_crafts()
    async with session_scope() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        craft = (await session.execute(select(Craft).where(Craft.slug == first))).scalar_one()
        session.add(
            ArtisanProfile(
                userId=user.id,
                districtLgd=DISTRICT_LGD,
                spokenLanguage="gu",
                creditMode="CRAFT_AND_DISTRICT",
                adultConfirmedAt=user.createdAt,
                completedAt=user.createdAt,
            )
        )
        await session.flush()
        session.add(ArtisanCraft(userId=user.id, craftId=craft.id, position=1))
    async with session_scope() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        await reader_profiles.apply_role_change(session, user, "STUDENT", objects=None)
        user.role = "STUDENT"
    async with session_scope() as session:
        assert await session.get(ArtisanProfile, user.id) is None
        assert (
            await session.scalar(select(ArtisanCraft.craftId).where(ArtisanCraft.userId == user.id)) is None
        )


async def test_places_are_public_and_cached_a_day(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/places/districts")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=86400"
    assert any(state["name"] == "Gujarat" for state in response.json()["states"])


async def test_me_says_what_is_owed_without_any_profile_value(client: httpx.AsyncClient) -> None:
    _, token = await signed_in(client, "STUDENT")
    owed = (await client.get("/api/auth/me", headers=bearer(token))).json()
    assert (owed["profileRequired"], owed["guardianConsentRequired"]) == (True, False)
    saved = await client.put(
        "/api/profile/me/student", json={"ageBand": "14_17", "gender": "ANOTHER"}, headers=bearer(token)
    )
    assert saved.json()["student"]["guardianConsent"] == "NEEDED"
    me = await client.get("/api/auth/me", headers=bearer(token))
    assert me.status_code == 200
    body = me.json()
    assert (body["profileRequired"], body["guardianConsentRequired"]) == (False, True)
    assert "14_17" not in me.text and "ANOTHER" not in me.text
