import uuid
from datetime import UTC, datetime, timedelta

from app.models import OAuthCode, OAuthGrant, User
from app.services.oauth_tokens import grant_matches_user

ENDED_AT = datetime(2026, 11, 19, 12, tzinfo=UTC)


def account(**changes: object) -> User:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "name": "Ravi Shah",
        "email": "ravi@example.org",
        "role": "RESEARCHER",
        "tokenVersion": 3,
        "sessionsValidFrom": ENDED_AT,
        "deletedAt": None,
    }
    values.update(changes)
    return User(**values)


def test_a_code_or_connection_made_before_sessions_were_ended_is_dead() -> None:
    before, after = ENDED_AT - timedelta(seconds=1), ENDED_AT + timedelta(seconds=1)
    assert not grant_matches_user(OAuthCode(userTokenVersion=3, createdAt=before), account())
    assert grant_matches_user(OAuthCode(userTokenVersion=3, createdAt=after), account())
    assert not grant_matches_user(OAuthGrant(userTokenVersion=3, createdAt=before), account())
    gone = account(deletedAt=ENDED_AT)
    assert not grant_matches_user(OAuthCode(userTokenVersion=3, createdAt=after), gone)


def test_a_code_or_connection_dies_when_the_account_s_token_version_moves() -> None:
    made = ENDED_AT + timedelta(minutes=1)
    for approved in (
        OAuthCode(userTokenVersion=3, createdAt=made),
        OAuthGrant(userTokenVersion=3, createdAt=made),
    ):
        assert grant_matches_user(approved, account())
        assert not grant_matches_user(approved, account(tokenVersion=4))
        assert not grant_matches_user(approved, None)
