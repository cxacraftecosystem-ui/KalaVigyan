import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import McpTermsAcceptance, McpToolCall, OAuthCode, OAuthGrant, OAuthToken, User
from app.research.oauth_contract import (
    AuthorizationPrompt,
    AuthorizationRedirect,
    AuthorizationRequest,
    ClientRegistration,
    Consent,
    TokenReply,
)
from app.research.oauth_metadata import OAuthEndpoints
from app.research.oauth_rules import MCP_TERMS_VERSION, Grantor, OAuthError
from app.services import oauth_bearer, oauth_clients, oauth_connections, oauth_consent, oauth_tokens
from app.services.oauth_bearer import BearerRefused

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 19, 12, tzinfo=UTC)
API = "https://api.kalavigyan.example"
RESOURCE = f"{API}/api/mcp"
ENDPOINTS = OAuthEndpoints(
    issuer=API,
    resource=RESOURCE,
    resource_metadata=f"{API}/.well-known/oauth-protected-resource/api/mcp",
    authorization="https://kalavigyan.example/oauth/authorize",
    token=f"{API}/api/oauth/token",
    registration=f"{API}/api/oauth/register",
    revocation=f"{API}/api/oauth/revoke",
)
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def grantor(user: User, *, signed_in_at: datetime | None = NOW) -> Grantor:
    return Grantor(user=user, signed_in_at=signed_in_at, now=NOW)


def sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        yield opened


async def person(session: AsyncSession, role: str = "RESEARCHER") -> User:
    key = uuid.uuid4()
    made = User(
        id=key,
        name=f"{role.title()} {key.hex[:4]}",
        email=f"{key.hex[:12]}@example.org",
        role=role,
        tokenVersion=0,
    )
    session.add(made)
    await session.flush()
    return made


async def registered(session: AsyncSession) -> str:
    made = await oauth_clients.register_client(
        session, ClientRegistration(redirect_uris=[REDIRECT], client_name="Claude"), now=NOW
    )
    return made.client_id


def asked(client_id: str, **changes: str) -> AuthorizationRequest:
    values = {
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "state": "xyz",
        "scope": "read contribute",
        "resource": RESOURCE,
        **changes,
    }
    return AuthorizationRequest.model_validate(values)


async def approved(
    session: AsyncSession, user: User, client_id: str, scopes: tuple[str, ...] = ("read", "contribute")
) -> str:
    consent = Consent(request=asked(client_id), scopes=list(scopes), terms_version=MCP_TERMS_VERSION)
    sent = await oauth_consent.approve(session, grantor(user), consent, endpoints=ENDPOINTS)
    query = parse_qs(urlsplit(sent.redirect_to).query)
    assert sent.redirect_to.startswith(f"{REDIRECT}?")
    assert (query["state"], query["iss"]) == (["xyz"], [API])
    return query["code"][0]


async def exchanged(
    session: AsyncSession, client_id: str, code: str, *, verifier: str = VERIFIER, at: datetime = NOW
) -> TokenReply:
    fields = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "code_verifier": verifier,
        "resource": RESOURCE,
    }
    return await oauth_tokens.grant_tokens(session, fields, resource=RESOURCE, now=at)


async def refreshed(
    session: AsyncSession, client_id: str, refresh_token: str, *, scope: str | None = None
) -> TokenReply:
    fields = {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id}
    if scope is not None:
        fields["scope"] = scope
    return await oauth_tokens.grant_tokens(session, fields, resource=RESOURCE, now=NOW + timedelta(minutes=1))


async def connected(session: AsyncSession, role: str = "RESEARCHER") -> tuple[User, str, TokenReply]:
    user = await person(session, role)
    client_id = await registered(session)
    reply = await exchanged(session, client_id, await approved(session, user, client_id))
    return user, client_id, reply


async def test_a_researcher_connects_an_agent_and_its_token_reaches_their_account(
    session: AsyncSession,
) -> None:
    user = await person(session)
    client_id = await registered(session)
    prompt = await oauth_consent.review(session, grantor(user), asked(client_id), endpoints=ENDPOINTS)
    assert isinstance(prompt, AuthorizationPrompt)
    assert (prompt.client_name, prompt.redirect_host, prompt.terms.accepted_at) == (
        "Claude",
        "claude.ai",
        None,
    )
    assert [(choice.scope, choice.allowed) for choice in prompt.scopes] == [
        ("read", True),
        ("contribute", True),
    ]
    code = await approved(session, user, client_id)
    stored = (await session.execute(select(OAuthCode))).scalars().all()
    assert [row.codeHash for row in stored if row.userId == user.id] == [sha256(code)]
    accepted = await session.execute(select(McpTermsAcceptance).where(McpTermsAcceptance.userId == user.id))
    assert [row.termsVersion for row in accepted.scalars()] == ["2026-11-19"]
    again = await oauth_consent.review(session, grantor(user), asked(client_id), endpoints=ENDPOINTS)
    assert isinstance(again, AuthorizationPrompt) and again.terms.accepted_at == NOW
    reply = await exchanged(session, client_id, code)
    assert (reply.scope, reply.expires_in, reply.token_type) == ("read contribute", 3600, "Bearer")
    hashes = set((await session.execute(select(OAuthToken.tokenHash))).scalars())
    assert {sha256(reply.access_token), sha256(reply.refresh_token)} <= hashes
    assert reply.access_token not in hashes
    caller = await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)
    assert (caller.user.id, caller.scopes) == (user.id, frozenset({"read", "contribute"}))
    listed = await oauth_connections.connections(session, user, now=NOW)
    assert [(item.client_name, item.client_host, item.scopes) for item in listed] == [
        ("Claude", "claude.ai", ["read", "contribute"])
    ]


async def test_a_code_works_once_and_its_reuse_revokes_the_connection(session: AsyncSession) -> None:
    user = await person(session)
    client_id = await registered(session)
    code = await approved(session, user, client_id)
    reply = await exchanged(session, client_id, code)
    with pytest.raises(OAuthError) as refused:
        await exchanged(session, client_id, code)
    assert refused.value.error == "invalid_grant"
    with pytest.raises(BearerRefused):
        await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)


async def test_a_wrong_verifier_or_a_code_older_than_five_minutes_is_invalid_grant(
    session: AsyncSession,
) -> None:
    user = await person(session)
    client_id = await registered(session)
    with pytest.raises(OAuthError) as wrong:
        await exchanged(session, client_id, await approved(session, user, client_id), verifier="a" * 43)
    late_code = await approved(session, user, client_id)
    with pytest.raises(OAuthError) as late:
        await exchanged(session, client_id, late_code, at=NOW + timedelta(minutes=6))
    assert (wrong.value.error, late.value.error) == ("invalid_grant", "invalid_grant")


async def test_a_code_dies_when_the_account_signs_out_everywhere_before_it_is_used(
    session: AsyncSession,
) -> None:
    user = await person(session)
    client_id = await registered(session)
    code = await approved(session, user, client_id)
    user.sessionsValidFrom = NOW + timedelta(seconds=30)
    await session.flush()
    with pytest.raises(OAuthError) as refused:
        await exchanged(session, client_id, code, at=NOW + timedelta(minutes=1))
    assert refused.value.error == "invalid_grant"


async def test_refresh_rotates_and_a_replayed_refresh_token_revokes_the_connection(
    session: AsyncSession,
) -> None:
    _user, client_id, first = await connected(session)
    second = await refreshed(session, client_id, first.refresh_token)
    assert second.refresh_token != first.refresh_token and second.access_token != first.access_token
    with pytest.raises(OAuthError) as replayed:
        await refreshed(session, client_id, first.refresh_token)
    assert replayed.value.error == "invalid_grant"
    with pytest.raises(BearerRefused):
        await oauth_bearer.caller_for(session, second.access_token, resource=RESOURCE, now=NOW)


async def test_refresh_may_narrow_the_scopes_but_never_widen_them(session: AsyncSession) -> None:
    _user, client_id, first = await connected(session)
    narrowed = await refreshed(session, client_id, first.refresh_token, scope="read")
    assert narrowed.scope == "read"
    with pytest.raises(OAuthError) as wider:
        await refreshed(session, client_id, narrowed.refresh_token, scope="read review")
    assert wider.value.error == "invalid_scope"


async def test_an_expired_token_a_foreign_resource_and_ended_sessions_are_refused(
    session: AsyncSession,
) -> None:
    user, _client_id, reply = await connected(session)
    with pytest.raises(BearerRefused) as expired:
        await oauth_bearer.caller_for(
            session, reply.access_token, resource=RESOURCE, now=NOW + timedelta(hours=2)
        )
    with pytest.raises(BearerRefused) as foreign:
        await oauth_bearer.caller_for(
            session, reply.access_token, resource="https://other.example/mcp", now=NOW
        )
    assert (expired.value.description, foreign.value.description) == (
        oauth_bearer.EXPIRED,
        oauth_bearer.FOREIGN,
    )
    user.tokenVersion += 1
    await session.flush()
    with pytest.raises(BearerRefused) as ended:
        await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)
    assert ended.value.description == oauth_bearer.ENDED


async def test_a_demoted_account_keeps_only_the_scopes_its_role_still_holds(session: AsyncSession) -> None:
    user, _client_id, reply = await connected(session)
    user.role = "STUDENT"
    await session.flush()
    caller = await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)
    assert caller.scopes == frozenset({"read"})


async def test_revoking_a_refresh_token_ends_the_connection_and_an_access_token_only_itself(
    session: AsyncSession,
) -> None:
    user, client_id, reply = await connected(session)
    await oauth_tokens.revoke_token(session, {"token": reply.access_token, "client_id": client_id}, now=NOW)
    with pytest.raises(BearerRefused):
        await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)
    assert len(await oauth_connections.connections(session, user, now=NOW)) == 1
    await oauth_tokens.revoke_token(session, {"token": reply.refresh_token, "client_id": client_id}, now=NOW)
    assert await oauth_connections.connections(session, user, now=NOW) == []
    await oauth_tokens.revoke_token(session, {"token": "kvmcp_at_unknown", "client_id": client_id}, now=NOW)


async def test_settings_revoke_only_your_own_connection(session: AsyncSession) -> None:
    user, _client_id, reply = await connected(session)
    stranger = await person(session)
    [connection] = await oauth_connections.connections(session, user, now=NOW)
    assert not await oauth_connections.revoke_connection(session, stranger, connection.id, now=NOW)
    assert await oauth_connections.revoke_connection(session, user, connection.id, now=NOW)
    assert await oauth_connections.connections(session, user, now=NOW) == []
    with pytest.raises(BearerRefused):
        await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)


async def test_connecting_the_same_app_again_replaces_the_first_connection(session: AsyncSession) -> None:
    user, client_id, first = await connected(session)
    await exchanged(session, client_id, await approved(session, user, client_id))
    with pytest.raises(BearerRefused):
        await oauth_bearer.caller_for(session, first.access_token, resource=RESOURCE, now=NOW)
    assert len(await oauth_connections.connections(session, user, now=NOW)) == 1


async def test_a_changed_terms_version_asks_again(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await person(session)
    client_id = await registered(session)
    await approved(session, user, client_id)
    monkeypatch.setattr(oauth_consent, "MCP_TERMS_VERSION", "2027-01-01")
    prompt = await oauth_consent.review(session, grantor(user), asked(client_id), endpoints=ENDPOINTS)
    assert isinstance(prompt, AuthorizationPrompt)
    assert (prompt.terms.version, prompt.terms.accepted_at) == ("2027-01-01", None)
    with pytest.raises(oauth_consent.TermsChanged):
        await approved(session, user, client_id)


async def test_untrusted_requests_stop_and_other_faults_return_to_the_app(session: AsyncSession) -> None:
    user = await person(session, "STUDENT")
    client_id = await registered(session)
    with pytest.raises(oauth_consent.UntrustedRequest):
        await oauth_consent.review(session, grantor(user), asked(str(uuid.uuid4())), endpoints=ENDPOINTS)
    with pytest.raises(oauth_consent.UntrustedRequest):
        await oauth_consent.review(
            session,
            grantor(user),
            asked(client_id, redirect_uri="https://evil.example/cb"),
            endpoints=ENDPOINTS,
        )
    wrong = await oauth_consent.review(
        session, grantor(user), asked(client_id, response_type="token"), endpoints=ENDPOINTS
    )
    assert isinstance(wrong, AuthorizationRedirect)
    query = parse_qs(urlsplit(wrong.redirect_to).query)
    assert (query["error"], query["state"]) == (["unsupported_response_type"], ["xyz"])
    with pytest.raises(InvalidInput):
        await approved(session, user, client_id)


async def test_each_tool_call_is_audited_per_connection_with_no_arguments_kept(session: AsyncSession) -> None:
    _user, _client_id, reply = await connected(session)
    caller = await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)
    later = NOW + timedelta(minutes=3)
    assert caller.client_name == "Claude"
    await oauth_bearer.record_tool_call(
        session, caller, tool="find_crafts", outcome="OK", reason=None, now=later
    )
    await session.flush()
    [call] = (
        await session.execute(select(McpToolCall).where(McpToolCall.grantId == caller.grant_id))
    ).scalars()
    assert (call.tool, call.outcome, call.tokenId, call.calledAt, call.clientName, call.reason) == (
        "find_crafts",
        "OK",
        caller.token_id,
        later,
        "Claude",
        None,
    )
    assert set(McpToolCall.__table__.columns.keys()) == {
        "id",
        "grantId",
        "tokenId",
        "clientName",
        "tool",
        "outcome",
        "reason",
        "calledAt",
    }
    grant = await session.get(OAuthGrant, caller.grant_id)
    assert grant is not None and grant.lastUsedAt == later
