import uuid

import pytest

from app.research.oauth_client_documents import (
    MetadataClient,
    cache_seconds,
    client_id_problem,
    is_client_id_url,
    is_metadata_client_key,
    metadata_client,
    metadata_client_key,
)
from app.research.oauth_rules import OAuthError

from .client_documents import (
    CLAUDE_DOCUMENT,
    CLAUDE_ID,
    CLAUDE_RETURN,
    VSCODE_DOCUMENT,
    VSCODE_ID,
    document_bytes,
)


def test_claude_published_identity_names_the_client_and_its_one_return_address() -> None:
    made = metadata_client(CLAUDE_ID, document_bytes(CLAUDE_DOCUMENT))
    assert made == MetadataClient(client_id=CLAUDE_ID, name="Claude", redirect_uris=(CLAUDE_RETURN,))
    assert made.host == "claude.ai"
    assert made.key.version == 5
    assert made.key != metadata_client_key(VSCODE_ID)


def test_a_native_client_lists_a_loopback_return_and_grant_types_kalavigyan_does_not_offer() -> None:
    made = metadata_client(VSCODE_ID, document_bytes(VSCODE_DOCUMENT))
    assert (made.name, made.redirect_uris, made.host) == (
        "Visual Studio Code",
        ("http://127.0.0.1:33418/", "https://vscode.dev/redirect"),
        "vscode.dev",
    )


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"client_id": "https://claude.ai/oauth/other-client"}, "another client_id"),
        ({"client_id": None}, "another client_id"),
        ({"client_name": None}, "client_name"),
        ({"client_name": ""}, "client_name"),
        ({"redirect_uris": []}, "redirect_uris"),
        ({"redirect_uris": ["http://claude.ai/api/mcp/auth_callback"]}, "same device"),
        ({"redirect_uris": ["javascript:alert(1)"]}, "javascript"),
        ({"redirect_uris": ["https://claude.ai/cb#part"]}, "fragment"),
        ({"token_endpoint_auth_method": "client_secret_basic"}, "public clients only"),
        ({"token_endpoint_auth_method": "private_key_jwt"}, "public clients only"),
        ({"token_endpoint_auth_methods_supported": ["private_key_jwt"]}, "public clients only"),
        ({"client_secret": "s3cret"}, "client secret"),
        ({"client_secret_expires_at": 0}, "client secret"),
    ],
)
def test_a_document_that_breaks_a_rule_is_refused_as_an_invalid_client(
    changes: dict[str, object], words: str
) -> None:
    with pytest.raises(OAuthError) as refused:
        metadata_client(CLAUDE_ID, document_bytes(CLAUDE_DOCUMENT, **changes))
    assert (refused.value.error, refused.value.status) == ("invalid_client", 400)
    assert words in refused.value.description


@pytest.mark.parametrize(
    ("body", "words"), [(b"<html>Claude</html>", "not JSON"), (b"[]", "not a JSON object")]
)
def test_a_body_that_is_not_one_json_object_is_refused(body: bytes, words: str) -> None:
    with pytest.raises(OAuthError) as refused:
        metadata_client(CLAUDE_ID, body)
    assert refused.value.error == "invalid_client"
    assert words in refused.value.description


def test_a_document_listing_one_return_twice_keeps_it_once() -> None:
    made = metadata_client(
        CLAUDE_ID, document_bytes(CLAUDE_DOCUMENT, redirect_uris=[CLAUDE_RETURN, CLAUDE_RETURN])
    )
    assert made.redirect_uris == (CLAUDE_RETURN,)


@pytest.mark.parametrize(
    ("client_id", "words"),
    [
        ("http://claude.ai/oauth/mcp-oauth-client-metadata", "https address"),
        ("https:///oauth/client.json", "https address"),
        ("https://claude.ai", "path"),
        ("https://claude.ai/", "path"),
        ("https://claude.ai/oauth/../client.json", "path"),
        ("https://claude.ai/./client.json", "path"),
        ("https://someone@claude.ai/client.json", "user name"),
        ("https://claude.ai/client.json#top", "fragment"),
        ("https://claude.ai:8443/client.json", "port 443"),
        ("https://claude.ai/client json", "without spaces"),
    ],
)
def test_a_client_id_that_is_not_a_plain_https_document_address_is_refused(
    client_id: str, words: str
) -> None:
    problem = client_id_problem(client_id)
    assert problem is not None and words in problem


def test_published_addresses_pass_and_only_addresses_are_read_as_client_id_urls() -> None:
    assert client_id_problem(CLAUDE_ID) is None
    assert client_id_problem(VSCODE_ID) is None
    assert client_id_problem("https://claude.ai:443/oauth/client.json") is None
    assert is_client_id_url(CLAUDE_ID)
    assert is_client_id_url("http://claude.ai/oauth/client.json")
    assert not is_client_id_url("5b1f7a9e-0000-4000-8000-000000000001")


def test_a_metadata_client_key_is_never_a_registered_clients_random_id() -> None:
    assert is_metadata_client_key(metadata_client_key(CLAUDE_ID))
    assert not is_metadata_client_key(uuid.UUID("5b1f7a9e-0000-4000-8000-000000000001"))
    assert metadata_client_key(CLAUDE_ID) == metadata_client_key(
        "https://claude.ai/oauth/mcp-oauth-client-metadata"
    )


@pytest.mark.parametrize(
    ("header", "seconds"),
    [
        (None, 600),
        ("", 600),
        ("max-age=3600", 3600),
        ("public, max-age=3600", 3600),
        ('max-age="900"', 900),
        ("Max-Age=1200, must-revalidate", 1200),
        ("max-age=30", 60),
        ("max-age=0", 60),
        ("max-age=604800", 86400),
        ("no-store", 60),
        ("no-cache, max-age=3600", 60),
        ("max-age=soon", 600),
    ],
)
def test_a_document_is_held_as_its_cache_headers_say_within_a_minute_and_a_day(
    header: str | None, seconds: int
) -> None:
    assert cache_seconds(header) == seconds
