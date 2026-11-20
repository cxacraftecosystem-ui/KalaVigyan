import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.services.page_preview_links import (
    LIVE_PREVIEWS_MAX,
    PREVIEW_LIFETIME,
    UnknownPreview,
    preview_key,
    preview_path,
    signed_token,
    token_preview,
)

KEY = b"k" * 32
PREVIEW = uuid.UUID("7a000000-0000-4000-8000-000000000001")
OWNER = uuid.UUID("7a000000-0000-4000-8000-000000000002")
STRANGER = uuid.UUID("7a000000-0000-4000-8000-000000000003")
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
EXPIRES = NOW + PREVIEW_LIFETIME


def test_a_preview_lives_a_day_and_an_account_keeps_twenty() -> None:
    assert timedelta(hours=24) == PREVIEW_LIFETIME
    assert LIVE_PREVIEWS_MAX == 20


def test_a_token_names_the_preview_and_its_end_and_is_signed_for_its_account() -> None:
    token = signed_token(PREVIEW, OWNER, EXPIRES, KEY)
    body = f"{PREVIEW.hex}.{int(EXPIRES.timestamp())}"
    mac = hmac.new(KEY, f"{body}.{OWNER.hex}".encode(), hashlib.sha256).hexdigest()
    assert token == f"{body}.{mac}"
    assert token_preview(token, OWNER, KEY, now=NOW) == PREVIEW
    assert preview_path(token) == f"/preview/{token}"


def test_another_account_an_ended_link_and_a_changed_token_are_all_unknown() -> None:
    token = signed_token(PREVIEW, OWNER, EXPIRES, KEY)
    with pytest.raises(UnknownPreview):
        token_preview(token, STRANGER, KEY, now=NOW)
    with pytest.raises(UnknownPreview):
        token_preview(token, OWNER, KEY, now=EXPIRES)
    later = signed_token(PREVIEW, OWNER, EXPIRES + timedelta(days=30), KEY).split(".")[1]
    forged = ".".join([PREVIEW.hex, later, token.split(".")[2]])
    with pytest.raises(UnknownPreview):
        token_preview(forged, OWNER, KEY, now=NOW)
    with pytest.raises(UnknownPreview):
        token_preview("kvpv_not-a-token", OWNER, KEY, now=NOW)
    with pytest.raises(UnknownPreview):
        token_preview(token, OWNER, b"another key" * 3, now=NOW)


def test_the_key_is_derived_from_the_signing_secret_and_never_is_it() -> None:
    key = preview_key()
    assert len(key) == hashlib.sha256().digest_size
    assert key == preview_key()
