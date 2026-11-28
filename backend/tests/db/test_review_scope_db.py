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


async def review_code(session: AsyncSession, user: User, client_id: str) -> str:
    consent = Consent(
        request=asked(client_id, scope=REVIEW_ASKED), scopes=["review"], terms_version=MCP_TERMS_VERSION
    )
    sent = await oauth_consent.approve(session, grantor(user), consent, endpoints=ENDPOINTS)
    return parse_qs(urlsplit(sent.redirect_to).query)["code"][0]


def refresh_fields(client_id: str, refresh_token: str) -> dict[str, str]:
    return {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id}


async def test_an_admin_with_two_step_gets_a_review_token_that_lives_an_hour_like_the_others(
    session: AsyncSession,
) -> None:
    admin = await account(session, "ADMIN", two_step=True)
    client_id = await registered(session)
    reply = await exchanged(session, client_id, await review_code(session, admin, client_id))
    assert (reply.scope, reply.expires_in) == ("read review", 3600)
    caller = await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)
    assert caller.scopes == frozenset({"read", "review"})
    admin.twoFactorEnabled = False
    await session.flush()
    later = await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)
    assert later.scopes == frozenset({"read"})


async def test_review_lasts_as_long_as_the_connection_and_refreshes_silently_for_a_year(
    session: AsyncSession,
) -> None:
    admin = await account(session, "MASTER_ADMIN", two_step=True)
    client_id = await registered(session)
    reply = await exchanged(session, client_id, await review_code(session, admin, client_id))
    used = NOW
    for days in (1, 30, 364, 700):
        used = NOW + timedelta(days=days)
        reply = await oauth_tokens.grant_tokens(
            session, refresh_fields(client_id, reply.refresh_token), resource=RESOURCE, now=used
        )
        assert (reply.scope, reply.expires_in) == ("read review", 3600)
    caller = await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=used)
    assert caller.scopes == frozenset({"read", "review"})
    [listed] = await oauth_connections.connections(session, admin, now=used + timedelta(days=200))
    assert listed.scopes == ["read", "review"]


@pytest.mark.parametrize(
    ("role", "two_step"),
    [("ADMIN", False), ("MASTER_ADMIN", False), ("PROFESSOR", True), ("RESEARCHER", True)],
)
async def test_review_is_refused_without_admin_and_two_step(
    session: AsyncSession, role: str, two_step: bool
) -> None:
    user = await account(session, role, two_step=two_step)
    client_id = await registered(session)
    prompt = await oauth_consent.review(
        session, grantor(user), asked(client_id, scope=REVIEW_ASKED), endpoints=ENDPOINTS
    )
    assert isinstance(prompt, AuthorizationPrompt)
    review = next(choice for choice in prompt.scopes if choice.scope == "review")
    assert review.allowed is False
    assert review.needs is not None and "two-step verification" in review.needs
    with pytest.raises(InvalidInput):
        await review_code(session, user, client_id)


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
    [later] = await oauth_connections.connections(session, admin, now=NOW + timedelta(days=90))
    assert later.scopes == ["read", "review"]
    admin.twoFactorEnabled = False
    admin.tokenVersion += 1
    await session.flush()
    with pytest.raises(BearerRefused) as ended:
        await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)
    assert ended.value.description == oauth_bearer.ENDED
    assert await oauth_connections.connections(session, admin, now=NOW) == []
