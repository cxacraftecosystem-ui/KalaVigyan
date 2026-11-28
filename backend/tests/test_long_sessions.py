import time
import uuid
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.deps import user_from_token
from app.core.security import (
    SESSION_ID_CLAIM,
    TOKEN_VERSION_CLAIM,
    create_access_token,
    decode_access_token,
    session_id_of,
)
from app.models import SiteSession, User

LIFETIME_NAMES = ("JWT_EXPIRES_MINUTES", "MCP_ACCESS_TOKEN_SECONDS", "MCP_REFRESH_TOKEN_SECONDS")
A_YEAR_IN_MINUTES = 525_600
A_YEAR_IN_SECONDS = 31_536_000
FOUR_HUNDRED_DAYS_IN_MINUTES = 576_000
SESSION = uuid.UUID("5e55105e-0000-4000-8000-000000000002")


@pytest.fixture
def lifetimes_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in LIFETIME_NAMES:
        monkeypatch.delenv(name, raising=False)


def settings(**values: object) -> Settings:
    return Settings(_env_file=None, **values)


@pytest.mark.usefixtures("lifetimes_unset")
def test_a_site_session_and_an_mcp_connection_last_a_year_and_an_mcp_access_token_an_hour() -> None:
    chosen = settings()
    assert chosen.jwt_expires_minutes == A_YEAR_IN_MINUTES
    assert chosen.mcp_refresh_token_seconds == A_YEAR_IN_SECONDS
    assert chosen.mcp_access_token_seconds == 3600


@pytest.mark.usefixtures("lifetimes_unset")
def test_each_lifetime_is_a_setting_and_a_session_never_outlives_the_browser_s_cookie_cap() -> None:
    assert settings(JWT_EXPIRES_MINUTES=FOUR_HUNDRED_DAYS_IN_MINUTES).jwt_expires_minutes == 576_000
    with pytest.raises(ValidationError):
        settings(JWT_EXPIRES_MINUTES=FOUR_HUNDRED_DAYS_IN_MINUTES + 1)
    with pytest.raises(ValidationError):
        settings(JWT_EXPIRES_MINUTES=0)
    assert settings(MCP_ACCESS_TOKEN_SECONDS=900).mcp_access_token_seconds == 900
    with pytest.raises(ValidationError):
        settings(MCP_ACCESS_TOKEN_SECONDS=86_401)
    assert settings(MCP_REFRESH_TOKEN_SECONDS=7200).mcp_refresh_token_seconds == 7200
    with pytest.raises(ValidationError):
        settings(MCP_REFRESH_TOKEN_SECONDS=60)


def test_a_session_token_names_its_session_and_lives_the_configured_lifetime() -> None:
    before = time.time()
    claims = decode_access_token(create_access_token("abc", token_version=2, session_id=SESSION))
    assert session_id_of(claims) == SESSION
    assert claims[SESSION_ID_CLAIM] == "5e55105e-0000-4000-8000-000000000002"
    lifetime = claims["exp"] - before
    minutes = get_settings().jwt_expires_minutes
    assert minutes * 60 - 5 <= lifetime <= minutes * 60 + 5
    with pytest.raises(ValueError):
        create_access_token("abc", token_version=2, session_id=SESSION, extra_claims={"sid": "other"})


def _signed(claims: dict[str, object]) -> str:
    return jwt.encode(claims, get_settings().jwt_secret, algorithm=get_settings().jwt_algorithm)


def test_a_token_from_before_session_ids_is_read_without_one_and_a_malformed_id_is_refused() -> None:
    base = {"sub": "abc", "exp": int(time.time()) + 600, TOKEN_VERSION_CLAIM: 0}
    assert session_id_of(decode_access_token(_signed(base))) is None
    for bad in ("not-a-uuid", 17, ["5e55105e-0000-4000-8000-000000000002"]):
        with pytest.raises(ValueError):
            decode_access_token(_signed({**base, SESSION_ID_CLAIM: bad}))


class Rows:
    def __init__(self, user: SimpleNamespace, record: SimpleNamespace | None) -> None:
        self.user, self.record = user, record
        self.asked: list[object] = []

    async def get(self, model: object, key: object) -> object:
        self.asked.append(model)
        return self.user if model is User else self.record


def account() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), tokenVersion=0, deletedAt=None, sessionsValidFrom=None)


async def test_a_token_is_good_only_while_its_session_is_live_and_its_own() -> None:
    person = account()
    token = create_access_token(str(person.id), token_version=0, session_id=SESSION)
    live = Rows(person, SimpleNamespace(id=SESSION, userId=person.id, endedAt=None))
    assert await user_from_token(live, token) is person
    assert live.asked == [User, SiteSession]
    ended = Rows(person, SimpleNamespace(id=SESSION, userId=person.id, endedAt=object()))
    foreign = Rows(person, SimpleNamespace(id=SESSION, userId=uuid.uuid4(), endedAt=None))
    for refused in (ended, foreign, Rows(person, None)):
        with pytest.raises(HTTPException) as caught:
            await user_from_token(refused, token)
        assert caught.value.status_code == 401


async def test_a_token_from_before_session_ids_stands_until_its_own_expiry() -> None:
    person = account()
    claims = {"sub": str(person.id), TOKEN_VERSION_CLAIM: 0}
    standing = Rows(person, None)
    assert await user_from_token(standing, _signed({**claims, "exp": int(time.time()) + 600})) is person
    assert standing.asked == [User]
    with pytest.raises(HTTPException) as caught:
        await user_from_token(Rows(person, None), _signed({**claims, "exp": int(time.time()) - 1}))
    assert caught.value.status_code == 401
