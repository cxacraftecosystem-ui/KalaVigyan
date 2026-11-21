import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.errors import InvalidInput
from app.research.oauth_contract import (
    AuthorizationPrompt,
    AuthorizationRedirect,
    Connection,
    RegisteredClient,
    TermsStatus,
    TokenReply,
)
from app.research.oauth_rules import OAuthError
from app.services import oauth_clients, oauth_connections, oauth_consent, oauth_tokens

from .oauth_fakes import API, RESOURCE, WEB, FakeSession, client, person, with_hosts

FORM = {"content-type": "application/x-www-form-urlencoded"}
AUTHORIZE_QUERY = {
    "client_id": "5b1f7a9e-0000-4000-8000-000000000001",
    "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
    "response_type": "code",
    "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
    "code_challenge_method": "S256",
    "state": "xyz",
}


def test_both_metadata_documents_name_the_api_as_issuer_and_the_web_page_for_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with_hosts(monkeypatch)
    http = client()
    expected_resource = {
        "resource": RESOURCE,
        "authorization_servers": [API],
        "scopes_supported": ["read", "ask", "contribute", "review"],
        "bearer_methods_supported": ["header"],
        "resource_name": "KalaVigyan",
    }
    for path in ("/.well-known/oauth-protected-resource/api/mcp", "/.well-known/oauth-protected-resource"):
        assert http.get(path).json() == expected_resource
    server = http.get("/.well-known/oauth-authorization-server").json()
    assert server["issuer"] == API
    assert server["authorization_endpoint"] == f"{WEB}/oauth/authorize"
    assert server["token_endpoint"] == f"{API}/api/oauth/token"
    assert server["registration_endpoint"] == f"{API}/api/oauth/register"
    assert server["revocation_endpoint"] == f"{API}/api/oauth/revoke"
    assert server["code_challenge_methods_supported"] == ["S256"]
    assert server["token_endpoint_auth_methods_supported"] == ["none"]
    assert server["grant_types_supported"] == ["authorization_code", "refresh_token"]
    assert server["response_types_supported"] == ["code"]
    assert server["client_id_metadata_document_supported"] is True


def test_metadata_is_404_while_the_server_is_off_and_503_without_an_https_api_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with_hosts(monkeypatch, enabled=False)
    assert client().get("/.well-known/oauth-authorization-server").status_code == 404
    with_hosts(monkeypatch, api=None)
    assert client().get("/.well-known/oauth-authorization-server").status_code == 503
    with_hosts(monkeypatch, api="http://api.kalavigyan.example")
    assert client().get("/.well-known/oauth-protected-resource").status_code == 503


def test_the_token_endpoint_takes_one_form_and_answers_rfc_6749_errors_unstored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with_hosts(monkeypatch)
    http = client()
    as_json = http.post("/api/oauth/token", json={"grant_type": "authorization_code"})
    assert (as_json.status_code, as_json.json()["error"]) == (400, "invalid_request")
    assert as_json.headers["cache-control"] == "no-store"
    twice = http.post("/api/oauth/token", content="grant_type=a&grant_type=b", headers=FORM)
    assert (twice.status_code, twice.json()["error"]) == (400, "invalid_request")


def test_the_token_endpoint_hands_the_form_on_and_replies_without_caching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with_hosts(monkeypatch)
    seen: dict[str, Any] = {}

    async def fake_grant(
        session: Any, fields: Mapping[str, str], *, resource: str, now: datetime
    ) -> TokenReply:
        seen.update(fields=dict(fields), resource=resource)
        return TokenReply(
            access_token="kvmcp_at_a", expires_in=3600, refresh_token="kvmcp_rt_b", scope="read ask"
        )

    monkeypatch.setattr(oauth_tokens, "grant_tokens", fake_grant)
    session = FakeSession()
    reply = client(session).post(
        "/api/oauth/token", content="grant_type=authorization_code&code=c1&scope=&client_id=x", headers=FORM
    )
    assert reply.status_code == 200
    assert reply.json() == {
        "access_token": "kvmcp_at_a",
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": "kvmcp_rt_b",
        "scope": "read ask",
    }
    assert (reply.headers["cache-control"], reply.headers["pragma"]) == ("no-store", "no-cache")
    assert seen == {
        "fields": {"grant_type": "authorization_code", "code": "c1", "client_id": "x"},
        "resource": RESOURCE,
    }
    assert session.commits == 1


def test_an_unknown_client_at_the_token_endpoint_is_401_invalid_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with_hosts(monkeypatch)

    async def refuse(*_: Any, **__: Any) -> TokenReply:
        raise OAuthError("invalid_client", "client_id is not registered", status=401)

    monkeypatch.setattr(oauth_tokens, "grant_tokens", refuse)
    reply = client().post("/api/oauth/token", content="grant_type=refresh_token", headers=FORM)
    assert (reply.status_code, reply.json()["error"]) == (401, "invalid_client")


def test_registration_refuses_bad_json_and_unsafe_redirects_and_is_limited_per_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with_hosts(monkeypatch)
    http = client()
    garbled = http.post("/api/oauth/register", content=b"{nope", headers={"content-type": "application/json"})
    assert (garbled.status_code, garbled.json()["error"]) == (400, "invalid_client_metadata")
    unsafe = http.post("/api/oauth/register", json={"redirect_uris": ["http://claude.ai/cb"]})
    assert (unsafe.status_code, unsafe.json()["error"]) == (400, "invalid_redirect_uri")
    for _ in range(18):
        http.post("/api/oauth/register", json={})
    assert http.post("/api/oauth/register", json={}).status_code == 429


def test_registration_answers_201_with_the_public_client(monkeypatch: pytest.MonkeyPatch) -> None:
    with_hosts(monkeypatch)
    made = RegisteredClient(
        client_id="5b1f7a9e-0000-4000-8000-000000000001",
        client_id_issued_at=1795046400,
        client_name="Claude",
        redirect_uris=["https://claude.ai/api/mcp/auth_callback"],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="none",
    )

    async def fake_register(*_: Any, **__: Any) -> RegisteredClient:
        return made

    monkeypatch.setattr(oauth_clients, "register_client", fake_register)
    reply = client().post(
        "/api/oauth/register", json={"redirect_uris": made.redirect_uris, "client_name": "Claude"}
    )
    assert reply.status_code == 201
    assert reply.json() == made.model_dump(exclude_none=True)


def test_the_consent_review_answers_the_prompt_in_camel_case(monkeypatch: pytest.MonkeyPatch) -> None:
    with_hosts(monkeypatch)
    prompt = AuthorizationPrompt(
        client_name="Claude",
        client_id_host="claude.ai",
        redirect_host="claude.ai",
        scopes=[],
        terms=TermsStatus(version="2026-11-19", accepted_at=None),
    )

    async def fake_review(*_: Any, **kwargs: Any) -> AuthorizationPrompt:
        assert kwargs["endpoints"].resource == RESOURCE
        return prompt

    monkeypatch.setattr(oauth_consent, "review", fake_review)
    reply = client(reader=person()).get("/api/oauth/authorize/request", params=AUTHORIZE_QUERY)
    assert reply.status_code == 200
    assert reply.json() == {
        "kind": "prompt",
        "clientName": "Claude",
        "clientIdHost": "claude.ai",
        "redirectHost": "claude.ai",
        "scopes": [],
        "terms": {"version": "2026-11-19", "acceptedAt": None},
    }


@pytest.mark.parametrize(
    ("refusal", "code"),
    [
        (oauth_consent.UntrustedRequest("This app is not registered."), 400),
        (oauth_consent.UntrustedRequest("Try again.", error="temporarily_unavailable", status=503), 503),
        (oauth_consent.TermsChanged("The terms changed."), 409),
        (InvalidInput("Your account may not give review."), 422),
    ],
)
def test_consent_refusals_are_answered_without_a_redirect(
    monkeypatch: pytest.MonkeyPatch, refusal: Exception, code: int
) -> None:
    with_hosts(monkeypatch)

    async def refuse(*_: Any, **__: Any) -> AuthorizationRedirect:
        raise refusal

    monkeypatch.setattr(oauth_consent, "approve", refuse)
    session = FakeSession()
    body = {"request": AUTHORIZE_QUERY, "scopes": ["read"], "termsVersion": "2026-11-19"}
    reply = client(session, reader=person()).post("/api/oauth/authorize/approve", json=body)
    assert (reply.status_code, reply.json()["detail"]) == (code, str(refusal))
    assert (session.commits, session.rollbacks) == (0, 1)


def test_connections_name_the_server_only_while_it_is_on(monkeypatch: pytest.MonkeyPatch) -> None:
    connected = Connection(
        id=uuid.UUID("5b1f7a9e-0000-4000-8000-0000000000aa"),
        client_name="Claude",
        client_host="claude.ai",
        scopes=["read", "ask"],
        connected_at=datetime(2026, 11, 19, 6, 30, tzinfo=UTC),
        last_used_at=None,
    )

    async def fake_connections(*_: Any, **__: Any) -> list[Connection]:
        return [connected]

    monkeypatch.setattr(oauth_connections, "connections", fake_connections)
    with_hosts(monkeypatch)
    listed = client(reader=person()).get("/api/oauth/connections").json()
    assert listed["serverUrl"] == RESOURCE
    assert listed["connections"][0] == {
        "id": "5b1f7a9e-0000-4000-8000-0000000000aa",
        "clientName": "Claude",
        "clientHost": "claude.ai",
        "scopes": ["read", "ask"],
        "connectedAt": "2026-11-19T06:30:00Z",
        "lastUsedAt": None,
    }
    with_hosts(monkeypatch, enabled=False)
    assert client(reader=person()).get("/api/oauth/connections").json()["serverUrl"] is None


def test_revoking_a_connection_that_is_not_yours_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    async def none_found(*_: Any, **__: Any) -> bool:
        return False

    monkeypatch.setattr(oauth_connections, "revoke_connection", none_found)
    reply = client(reader=person()).delete("/api/oauth/connections/5b1f7a9e-0000-4000-8000-0000000000aa")
    assert reply.status_code == 404


def test_the_terms_are_served_with_their_version() -> None:
    terms = client().get("/api/oauth/terms").json()
    assert terms["version"] == "2026-11-19"
    assert terms["title"] == "MCP terms of use"
    assert terms["body"].startswith("## What you may do")
