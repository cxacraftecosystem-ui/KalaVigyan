from collections.abc import AsyncIterator
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import User
from app.research.oauth_contract import AuthorizationPrompt, Consent
from app.research.oauth_rules import MCP_TERMS_VERSION
from app.services import oauth_bearer, oauth_connections, oauth_consent, oauth_tokens
from app.services.oauth_bearer import BearerRefused

from .test_oauth_db import ENDPOINTS, NOW, RESOURCE, asked, connected, exchanged, grantor, person, registered
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

REVIEW_ASKED = "read contribute review"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        yield opened


async def account(session: AsyncSession, role: str, *, two_step: bool) -> User:
    made = await person(session, role)
    made.twoFactorEnabled = two_step
    await session.flush()
    return made


async def review_code(session: AsyncSession, user: User, client_id: str, *, minutes_ago: int = 5) -> str:
    consent = Consent(
        request=asked(client_id, scope=REVIEW_ASKED), scopes=["review"], terms_version=MCP_TERMS_VERSION
    )
    who = grantor(user, signed_in_at=NOW - timedelta(minutes=minutes_ago))
    sent = await oauth_consent.approve(session, who, consent, endpoints=ENDPOINTS)
    return parse_qs(urlsplit(sent.redirect_to).query)["code"][0]


async def test_an_admin_with_two_step_who_signed_in_recently_gets_a_short_review_token(
    session: AsyncSession,
) -> None:
    admin = await account(session, "ADMIN", two_step=True)
    client_id = await registered(session)
    reply = await exchanged(session, client_id, await review_code(session, admin, client_id))
    assert (reply.scope, reply.expires_in) == ("read review", 900)
    caller = await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)
    assert caller.scopes == frozenset({"read", "review"})
    admin.twoFactorEnabled = False
    await session.flush()
    later = await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)
    assert later.scopes == frozenset({"read"})


async def test_review_ends_eight_hours_after_the_grant_and_the_connection_goes_on(
    session: AsyncSession,
) -> None:
    admin = await account(session, "MASTER_ADMIN", two_step=True)
    client_id = await registered(session)
    reply = await exchanged(session, client_id, await review_code(session, admin, client_id))
    fields = {"grant_type": "refresh_token", "refresh_token": reply.refresh_token, "client_id": client_id}
    renewed = await oauth_tokens.grant_tokens(
        session, fields, resource=RESOURCE, now=NOW + timedelta(hours=8, minutes=1)
    )
    assert (renewed.scope, renewed.expires_in) == ("read", 3600)


@pytest.mark.parametrize(
    ("role", "two_step", "minutes_ago"),
    [("ADMIN", False, 5), ("ADMIN", True, 16), ("PROFESSOR", True, 5), ("RESEARCHER", True, 5)],
)
async def test_review_is_refused_without_admin_two_step_and_a_recent_sign_in(
    session: AsyncSession, role: str, two_step: bool, minutes_ago: int
) -> None:
    user = await account(session, role, two_step=two_step)
    client_id = await registered(session)
    who = grantor(user, signed_in_at=NOW - timedelta(minutes=minutes_ago))
    prompt = await oauth_consent.review(
        session, who, asked(client_id, scope=REVIEW_ASKED), endpoints=ENDPOINTS
    )
    assert isinstance(prompt, AuthorizationPrompt)
    review = next(choice for choice in prompt.scopes if choice.scope == "review")
    assert review.allowed is False
    assert review.needs is not None and "two-step verification" in review.needs
    with pytest.raises(InvalidInput):
        await review_code(session, user, client_id, minutes_ago=minutes_ago)


async def test_connected_apps_lists_only_connections_the_server_still_serves(session: AsyncSession) -> None:
    user, _client_id, _reply = await connected(session)
    assert len(await oauth_connections.connections(session, user, now=NOW)) == 1
    user.role = "STUDENT"
    await session.flush()
    [demoted] = await oauth_connections.connections(session, user, now=NOW)
    assert demoted.scopes == ["read"]
    user.tokenVersion += 1
    await session.flush()
    assert await oauth_connections.connections(session, user, now=NOW) == []
    other, _other_client, _other_reply = await connected(session)
    other.sessionsValidFrom = NOW + timedelta(seconds=30)
    await session.flush()
    assert await oauth_connections.connections(session, other, now=NOW + timedelta(minutes=1)) == []


async def test_review_ends_with_the_connection_when_two_step_changes_and_lists_as_it_holds(
    session: AsyncSession,
) -> None:
    admin = await account(session, "ADMIN", two_step=True)
    client_id = await registered(session)
    reply = await exchanged(session, client_id, await review_code(session, admin, client_id))
    [listed] = await oauth_connections.connections(session, admin, now=NOW)
    assert listed.scopes == ["read", "review"]
    [later] = await oauth_connections.connections(session, admin, now=NOW + timedelta(hours=8))
    assert later.scopes == ["read"]
    admin.twoFactorEnabled = False
    admin.tokenVersion += 1
    await session.flush()
    with pytest.raises(BearerRefused) as ended:
        await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)
    assert ended.value.description == oauth_bearer.ENDED
    assert await oauth_connections.connections(session, admin, now=NOW) == []
