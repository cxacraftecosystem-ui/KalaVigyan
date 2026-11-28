import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OAuthGrant, OAuthToken
from app.research.oauth_contract import TokenReply
from app.research.oauth_rules import OAuthError
from app.services import oauth_bearer, oauth_connections, oauth_tokens
from app.services.oauth_bearer import BearerRefused

from .test_oauth_db import NOW, RESOURCE, connected
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

YEAR = timedelta(days=365)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        yield opened


async def refreshed_at(session: AsyncSession, client_id: str, refresh_token: str, at: datetime) -> TokenReply:
    fields = {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id}
    return await oauth_tokens.grant_tokens(session, fields, resource=RESOURCE, now=at)


async def grant_of(session: AsyncSession, client_id: str) -> OAuthGrant:
    found = await session.execute(
        select(OAuthGrant).where(OAuthGrant.clientId == uuid.UUID(client_id), OAuthGrant.revokedAt.is_(None))
    )
    return found.scalar_one()


async def test_a_refresh_token_lives_a_year_from_its_last_use_and_rotates_each_time(
    session: AsyncSession,
) -> None:
    _user, client_id, first = await connected(session)
    used = NOW + timedelta(days=200)
    second = await refreshed_at(session, client_id, first.refresh_token, used)
    assert second.refresh_token != first.refresh_token and second.expires_in == 3600
    assert (await grant_of(session, client_id)).expiresAt == used + YEAR
    later = used + YEAR - timedelta(minutes=1)
    third = await refreshed_at(session, client_id, second.refresh_token, later)
    assert third.refresh_token not in (first.refresh_token, second.refresh_token)
    with pytest.raises(OAuthError) as lapsed:
        await refreshed_at(session, client_id, third.refresh_token, later + YEAR + timedelta(minutes=1))
    assert lapsed.value.error == "invalid_grant"


async def test_an_untouched_connection_ends_a_year_after_its_last_use(session: AsyncSession) -> None:
    user, client_id, first = await connected(session)
    assert len(await oauth_connections.connections(session, user, now=NOW + YEAR - timedelta(days=1))) == 1
    assert await oauth_connections.connections(session, user, now=NOW + YEAR + timedelta(days=1)) == []
    with pytest.raises(OAuthError):
        await refreshed_at(session, client_id, first.refresh_token, NOW + YEAR + timedelta(days=1))


async def test_a_refresh_token_reused_months_after_it_was_spent_revokes_the_whole_chain(
    session: AsyncSession,
) -> None:
    user, client_id, first = await connected(session)
    second = await refreshed_at(session, client_id, first.refresh_token, NOW + timedelta(days=100))
    third = await refreshed_at(session, client_id, second.refresh_token, NOW + timedelta(days=300))
    replay_at = NOW + timedelta(days=300, minutes=10)
    live = await oauth_bearer.caller_for(session, third.access_token, resource=RESOURCE, now=replay_at)
    assert live.scopes == frozenset({"read", "contribute"})
    with pytest.raises(OAuthError) as reused:
        await refreshed_at(session, client_id, first.refresh_token, replay_at)
    assert (reused.value.error, reused.value.description) == ("invalid_grant", oauth_tokens.REUSED)
    with pytest.raises(BearerRefused) as revoked:
        await oauth_bearer.caller_for(session, third.access_token, resource=RESOURCE, now=replay_at)
    assert revoked.value.description == oauth_bearer.UNKNOWN
    with pytest.raises(OAuthError):
        await refreshed_at(session, client_id, third.refresh_token, replay_at)
    assert await oauth_connections.connections(session, user, now=replay_at) == []


async def test_a_connection_made_under_the_thirty_day_rule_gains_the_year_at_its_next_refresh(
    session: AsyncSession,
) -> None:
    _user, client_id, first = await connected(session)
    grant = await grant_of(session, client_id)
    thirty_days = NOW + timedelta(days=30)
    await session.execute(update(OAuthGrant).where(OAuthGrant.id == grant.id).values(expiresAt=thirty_days))
    await session.execute(
        update(OAuthToken)
        .where(OAuthToken.grantId == grant.id, OAuthToken.kind == oauth_tokens.REFRESH)
        .values(expiresAt=thirty_days)
    )
    caller = await oauth_bearer.caller_for(session, first.access_token, resource=RESOURCE, now=NOW)
    assert caller.scopes == frozenset({"read", "contribute"})
    used = NOW + timedelta(days=29)
    renewed = await refreshed_at(session, client_id, first.refresh_token, used)
    await session.refresh(grant)
    assert grant.expiresAt == used + YEAR
    assert (
        await oauth_bearer.caller_for(session, renewed.access_token, resource=RESOURCE, now=used)
    ).scopes == (frozenset({"read", "contribute"}))
