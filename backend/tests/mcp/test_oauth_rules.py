from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core.errors import InvalidInput
from app.research.oauth_authorization import checked_authorization, granted_scopes
from app.research.oauth_contract import AuthorizationRequest, ClientRegistration, registered_client
from app.research.oauth_rules import (
    Grantor,
    OAuthError,
    access_token_seconds,
    challenge_is_valid,
    held_scopes,
    live_scopes,
    pkce_matches,
    redirect_uri_matches,
    redirect_uri_problem,
    redirect_with,
    requested_scopes,
    s256_challenge,
    verifier_is_valid,
)

RFC7636_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
RFC7636_CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
RESOURCE = "https://api.kalavigyan.example/api/mcp"
NOW = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)


def account(role: str, *, two_step: bool = True) -> SimpleNamespace:
    return SimpleNamespace(role=role, twoFactorEnabled=two_step)


def grantor(role: str, *, two_step: bool = True, minutes_ago: int | None = 5) -> Grantor:
    signed_in = None if minutes_ago is None else NOW - timedelta(minutes=minutes_ago)
    return Grantor(user=account(role, two_step=two_step), signed_in_at=signed_in, now=NOW)


def authorization(**changes: str | None) -> AuthorizationRequest:
    values: dict[str, str | None] = {
        "client_id": "5b1f7a9e-0000-4000-8000-000000000001",
        "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
        "response_type": "code",
        "code_challenge": RFC7636_CHALLENGE,
        "code_challenge_method": "S256",
        "state": "xyz",
        "scope": "read ask",
        "resource": RESOURCE,
    }
    values.update(changes)
    return AuthorizationRequest.model_validate(values)


def test_the_s256_challenge_is_the_rfc_7636_appendix_b_example() -> None:
    assert s256_challenge(RFC7636_VERIFIER) == RFC7636_CHALLENGE
    assert pkce_matches(RFC7636_VERIFIER, RFC7636_CHALLENGE)
    assert not pkce_matches(RFC7636_VERIFIER[:-1] + "Y", RFC7636_CHALLENGE)


@pytest.mark.parametrize(
    ("verifier", "valid"),
    [("a" * 42, False), ("a" * 43, True), ("a" * 128, True), ("a" * 129, False), ("a" * 42 + "+", False)],
)
def test_a_verifier_is_43_to_128_unreserved_characters(verifier: str, valid: bool) -> None:
    assert verifier_is_valid(verifier) is valid


def test_a_challenge_is_43_base64url_characters_and_plain_is_never_matched() -> None:
    assert challenge_is_valid(RFC7636_CHALLENGE)
    assert not challenge_is_valid(RFC7636_CHALLENGE + "=")
    assert not challenge_is_valid(RFC7636_CHALLENGE[:-1] + "+")
    assert not pkce_matches(RFC7636_VERIFIER, RFC7636_VERIFIER)


@pytest.mark.parametrize(
    "uri",
    [
        "https://claude.ai/api/mcp/auth_callback",
        "http://127.0.0.1:33418/callback",
        "http://[::1]/callback",
        "http://localhost:6274/oauth/callback",
        "cursor://anysphere.cursor-retrieval/oauth/callback",
    ],
)
def test_https_loopback_http_and_native_app_schemes_may_be_registered(uri: str) -> None:
    assert redirect_uri_problem(uri) is None


@pytest.mark.parametrize(
    "uri",
    [
        "http://claude.ai/callback",
        "https://claude.ai/callback#fragment",
        "javascript:alert(1)",
        "data:text/html,hi",
        "/relative/callback",
        "https://user:pw@claude.ai/callback",
        "https://claude.ai/call back",
        "",
    ],
)
def test_plain_http_fragments_script_schemes_relative_and_credentials_are_refused(uri: str) -> None:
    assert redirect_uri_problem(uri) is not None


def test_a_loopback_redirect_may_change_its_port_and_nothing_else_may_change() -> None:
    registered = "http://127.0.0.1/callback"
    assert redirect_uri_matches(registered, "http://127.0.0.1:51234/callback")
    assert not redirect_uri_matches(registered, "http://127.0.0.1:51234/other")
    assert not redirect_uri_matches(registered, "http://127.0.0.2:51234/callback")
    https = "https://claude.ai/api/mcp/auth_callback"
    assert redirect_uri_matches(https, https)
    assert not redirect_uri_matches(https, "https://claude.ai:8443/api/mcp/auth_callback")
    assert not redirect_uri_matches(https, "https://claude.ai/api/mcp/auth_callback?x=1")


def test_the_reply_keeps_the_redirect_s_own_query_and_adds_code_state_and_issuer() -> None:
    sent = redirect_with(
        "https://claude.ai/api/mcp/auth_callback?x=1",
        {"code": "abc", "state": "s t", "iss": "https://api.kalavigyan.example", "error": None},
    )
    assert sent == (
        "https://claude.ai/api/mcp/auth_callback?x=1&code=abc&state=s+t&iss=https%3A%2F%2Fapi.kalavigyan.example"
    )


def test_read_is_always_asked_and_scopes_come_in_their_fixed_order() -> None:
    assert requested_scopes(None) == ("read",)
    assert requested_scopes("") == ("read",)
    assert requested_scopes("review ask ask") == ("read", "ask", "review")
    with pytest.raises(OAuthError) as refused:
        requested_scopes("read admin")
    assert refused.value.error == "invalid_scope"


def test_offline_access_is_accepted_and_grants_nothing_more_since_refresh_tokens_always_come() -> None:
    assert requested_scopes("offline_access") == ("read",)
    assert requested_scopes("read offline_access contribute") == ("read", "contribute")


@pytest.mark.parametrize(
    ("role", "held"),
    [
        ("STUDENT", ("read", "ask")),
        ("ARTISAN", ("read", "ask")),
        ("RESEARCHER", ("read", "ask", "contribute")),
        ("PROFESSOR", ("read", "ask", "contribute")),
        ("ADMIN", ("read", "ask", "contribute", "review")),
        ("MASTER_ADMIN", ("read", "ask", "contribute", "review")),
        ("UNKNOWN", ("read",)),
    ],
)
def test_review_is_for_admins_with_two_step_on_and_contribute_needs_propose_knowledge(
    role: str, held: tuple[str, ...]
) -> None:
    assert held_scopes(account(role), ("read", "ask", "contribute", "review")) == held
    without_two_step = tuple(scope for scope in held if scope != "review")
    assert held_scopes(account(role, two_step=False), ("read", "ask", "contribute", "review")) == (
        without_two_step
    )
    assert "review" not in held_scopes(role, ("read", "review"))


@pytest.mark.parametrize(
    ("who", "may"),
    [
        (grantor("ADMIN", minutes_ago=5), True),
        (grantor("MASTER_ADMIN", minutes_ago=15), True),
        (grantor("ADMIN", minutes_ago=16), False),
        (grantor("ADMIN", minutes_ago=None), False),
        (grantor("ADMIN", two_step=False), False),
        (grantor("PROFESSOR"), False),
        (grantor("RESEARCHER"), False),
    ],
)
def test_review_is_granted_only_by_an_admin_with_two_step_who_signed_in_within_fifteen_minutes(
    who: Grantor, may: bool
) -> None:
    assert who.may_grant("review") is may
    assert who.may_grant("read") is True


def test_a_review_token_lives_fifteen_minutes_and_review_ends_eight_hours_after_the_grant() -> None:
    assert access_token_seconds(("read", "review")) == 900
    assert access_token_seconds(("read", "contribute")) == 3600
    granted = NOW - timedelta(hours=8)
    assert live_scopes(("read", "contribute", "review"), granted_at=granted, now=NOW) == (
        "read",
        "contribute",
    )
    soon = NOW - timedelta(hours=7, minutes=59)
    assert live_scopes(("review", "read"), granted_at=soon, now=NOW) == ("read", "review")


def test_an_authorization_request_needs_code_s256_and_this_resource() -> None:
    checked = checked_authorization(authorization(), resource=RESOURCE)
    assert (checked.scopes, checked.challenge, checked.resource) == (
        ("read", "ask"),
        RFC7636_CHALLENGE,
        RESOURCE,
    )
    assert checked_authorization(authorization(resource=None), resource=RESOURCE).resource == RESOURCE
    cases = {
        "unsupported_response_type": authorization(response_type="token"),
        "invalid_request": authorization(code_challenge_method="plain"),
        "invalid_target": authorization(resource="https://elsewhere.example/mcp"),
    }
    for error, request in cases.items():
        with pytest.raises(OAuthError) as refused:
            checked_authorization(request, resource=RESOURCE)
        assert refused.value.error == error
    with pytest.raises(OAuthError):
        checked_authorization(authorization(code_challenge=None), resource=RESOURCE)


def test_a_person_grants_only_what_was_asked_and_what_their_role_holds() -> None:
    assert granted_scopes(grantor("RESEARCHER"), ("read", "ask", "contribute"), ("contribute",)) == (
        "read",
        "contribute",
    )
    assert granted_scopes(grantor("ADMIN"), ("read", "review"), ("review",)) == ("read", "review")
    with pytest.raises(InvalidInput):
        granted_scopes(grantor("ADMIN"), ("read", "ask"), ("review",))
    with pytest.raises(InvalidInput):
        granted_scopes(grantor("PROFESSOR"), ("read", "review"), ("review",))
    with pytest.raises(InvalidInput):
        granted_scopes(grantor("ADMIN", minutes_ago=30), ("read", "review"), ("review",))
    with pytest.raises(InvalidInput):
        granted_scopes(grantor("ADMIN", two_step=False), ("read", "review"), ("review",))
    with pytest.raises(InvalidInput):
        granted_scopes(grantor("STUDENT"), ("read", "contribute"), ("contribute",))


def test_registration_is_for_public_clients_with_safe_redirects() -> None:
    fields = registered_client(
        ClientRegistration.model_validate(
            {
                "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"] * 2,
                "grant_types": ["authorization_code", "refresh_token"],
                "token_endpoint_auth_method": "none",
                "logo_uri": "https://claude.ai/logo.png",
            }
        )
    )
    assert fields["redirectUris"] == ["https://claude.ai/api/mcp/auth_callback"]
    assert fields["name"] == "claude.ai"
    refusals = {
        "invalid_redirect_uri": {"redirect_uris": ["http://claude.ai/callback"]},
        "invalid_client_metadata": {
            "redirect_uris": ["https://claude.ai/cb"],
            "token_endpoint_auth_method": "client_secret_basic",
        },
    }
    for error, body in refusals.items():
        with pytest.raises(OAuthError) as refused:
            registered_client(ClientRegistration.model_validate(body))
        assert refused.value.error == error
    with pytest.raises(OAuthError):
        registered_client(
            ClientRegistration.model_validate(
                {"redirect_uris": ["https://a.example/cb"], "grant_types": ["password"]}
            )
        )
