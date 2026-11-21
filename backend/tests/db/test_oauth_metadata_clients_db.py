import uuid
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OAuthClient, OAuthCode
from app.research.oauth_client_documents import metadata_client_key
from app.research.oauth_contract import AuthorizationPrompt, ClientRegistration, Consent
from app.research.oauth_rules import MCP_TERMS_VERSION, OAuthError
from app.services import oauth_bearer, oauth_client_documents, oauth_clients, oauth_connections, oauth_consent
from app.services.oauth_client_documents import ClientDocuments, FetchedDocument

from ..mcp.client_documents import CLAUDE_DOCUMENT, CLAUDE_ID, CLAUDE_RETURN, document_bytes
from .test_oauth_db import API, ENDPOINTS, NOW, RESOURCE, asked, exchanged, person, refreshed
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        yield opened


def publish(monkeypatch: pytest.MonkeyPatch, documents: dict[str, dict[str, Any]]) -> list[str]:
    reads: list[str] = []

    async def read(url: str) -> FetchedDocument:
        reads.append(url)
        return FetchedDocument(document_bytes(documents[url]), "max-age=3600")

    monkeypatch.setattr(oauth_client_documents, "CLIENT_DOCUMENTS", ClientDocuments(read=read))
    return reads


def an_app(name: str = "Example agent") -> tuple[str, dict[str, Any]]:
    address = f"https://apps.example.org/clients/{uuid.uuid4().hex}.json"
    return address, {"client_id": address, "client_name": name, "redirect_uris": [CLAUDE_RETURN]}


async def approve(session: AsyncSession, user: Any, client_id: str, **changes: str) -> str:
    consent = Consent(
        request=asked(client_id, **changes), scopes=["read", "contribute"], terms_version=MCP_TERMS_VERSION
    )
    sent = await oauth_consent.approve(session, user, consent, endpoints=ENDPOINTS, now=NOW)
    query = parse_qs(urlsplit(sent.redirect_to).query)
    assert sent.redirect_to.startswith(f"{CLAUDE_RETURN}?") and query["iss"] == [API]
    return query["code"][0]


async def test_claude_signs_in_with_its_published_identity_and_its_token_reaches_the_account(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads = publish(monkeypatch, {CLAUDE_ID: CLAUDE_DOCUMENT})
    user = await person(session)
    prompt = await oauth_consent.review(session, user, asked(CLAUDE_ID), endpoints=ENDPOINTS)
    assert isinstance(prompt, AuthorizationPrompt)
    assert (prompt.client_name, prompt.client_id_host, prompt.redirect_host) == (
        "Claude",
        "claude.ai",
        "claude.ai",
    )
    code = await approve(session, user, CLAUDE_ID)
    [stored] = (await session.execute(select(OAuthCode).where(OAuthCode.userId == user.id))).scalars()
    assert stored.clientId == metadata_client_key(CLAUDE_ID)
    reply = await exchanged(session, CLAUDE_ID, code)
    assert reply.scope == "read contribute"
    caller = await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)
    assert (caller.user.id, caller.scopes) == (user.id, frozenset({"read", "contribute"}))
    again = await refreshed(session, CLAUDE_ID, reply.refresh_token)
    assert again.refresh_token != reply.refresh_token
    listed = await oauth_connections.connections(session, user, now=NOW)
    assert [(item.client_name, item.client_host) for item in listed] == [("Claude", "claude.ai")]
    assert reads == [CLAUDE_ID]


async def test_a_return_address_the_document_does_not_list_stops_the_sign_in(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    address, document = an_app()
    publish(monkeypatch, {address: document})
    user = await person(session)
    with pytest.raises(oauth_consent.UntrustedRequest) as stopped:
        await oauth_consent.review(
            session, user, asked(address, redirect_uri="https://evil.example/cb"), endpoints=ENDPOINTS
        )
    assert (stopped.value.error, stopped.value.status) == ("invalid_request", 400)
    with pytest.raises(oauth_consent.UntrustedRequest):
        await approve(session, user, address, redirect_uri="https://evil.example/cb")
    assert await session.get(OAuthClient, metadata_client_key(address)) is None


async def test_a_document_naming_another_client_stops_the_sign_in_as_an_invalid_client(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    address, document = an_app()
    publish(monkeypatch, {address: document | {"client_id": "https://apps.example.org/someone-else.json"}})
    user = await person(session)
    with pytest.raises(oauth_consent.UntrustedRequest) as stopped:
        await oauth_consent.review(session, user, asked(address), endpoints=ENDPOINTS)
    assert (stopped.value.error, stopped.value.status) == ("invalid_client", 400)


async def test_everyone_connecting_one_app_shares_its_row_and_a_new_name_reaches_it(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    address, document = an_app("Example agent")
    publish(monkeypatch, {address: document})
    first, second = await person(session), await person(session)
    await exchanged(session, address, await approve(session, first, address))
    publish(monkeypatch, {address: document | {"client_name": "Example agent 2"}})
    await exchanged(session, address, await approve(session, second, address))
    key = metadata_client_key(address)
    rows = await session.execute(select(OAuthClient.name, OAuthClient.clientUri).where(OAuthClient.id == key))
    assert rows.all() == [("Example agent 2", address)]
    assert len(await oauth_connections.connections(session, first, now=NOW)) == 1
    assert len(await oauth_connections.connections(session, second, now=NOW)) == 1


async def test_dynamic_registration_still_signs_in_beside_published_identities(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    address, document = an_app()
    reads = publish(monkeypatch, {address: document})
    user = await person(session)
    registered = await oauth_clients.register_client(
        session, ClientRegistration(redirect_uris=[CLAUDE_RETURN], client_name="Claude"), now=NOW
    )
    assert uuid.UUID(registered.client_id).version == 4
    prompt = await oauth_consent.review(session, user, asked(registered.client_id), endpoints=ENDPOINTS)
    assert isinstance(prompt, AuthorizationPrompt)
    assert (prompt.client_name, prompt.client_id_host) == ("Claude", None)
    reply = await exchanged(session, registered.client_id, await approve(session, user, registered.client_id))
    caller = await oauth_bearer.caller_for(session, reply.access_token, resource=RESOURCE, now=NOW)
    assert caller.user.id == user.id
    await exchanged(session, address, await approve(session, user, address))
    listed = await oauth_connections.connections(session, user, now=NOW)
    assert sorted((item.client_name, item.client_host) for item in listed) == [
        ("Claude", "claude.ai"),
        ("Example agent", "apps.example.org"),
    ]
    assert reads == [address]


async def test_the_token_endpoint_knows_a_published_identity_only_by_its_address_once_approved(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    address, document = an_app()
    publish(monkeypatch, {address: document})
    user = await person(session)
    never = "https://apps.example.org/clients/never-approved.json"
    for client_id in (never, str(metadata_client_key(address))):
        with pytest.raises(OAuthError) as refused:
            await exchanged(session, client_id, "kvmcp_ac_unknown")
        assert (refused.value.error, refused.value.status) == ("invalid_client", 401)
    code = await approve(session, user, address)
    with pytest.raises(OAuthError) as by_key:
        await exchanged(session, str(metadata_client_key(address)), code)
    assert by_key.value.error == "invalid_client"
    assert (await exchanged(session, address, code)).scope == "read contribute"
