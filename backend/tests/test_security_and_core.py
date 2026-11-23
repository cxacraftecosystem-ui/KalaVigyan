import base64
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest

from app.core import security
from app.core.config import get_settings, with_explicit_sslmode
from app.core.db import build_runtime_database_url
from app.core.deps import token_matches_user
from app.core.logging import redact_secrets
from app.core.security import (
    TOKEN_VERSION_CLAIM,
    create_access_token,
    decode_access_token,
    hash_password,
    jwt_signing_weakness,
    verify_password,
    verify_password_or_decoy,
)
from app.services import auth_nonces, google_auth, two_factor


def test_password_round_trip() -> None:
    hashed = hash_password("correct horse battery")
    assert verify_password("correct horse battery", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password_or_decoy("anything", None)


def test_password_refuses_nul() -> None:
    with pytest.raises(ValueError):
        hash_password("a\x00b")


def test_weak_jwt_secrets() -> None:
    assert jwt_signing_weakness("")
    assert jwt_signing_weakness("change-me")
    assert jwt_signing_weakness("short")
    assert jwt_signing_weakness("x" * 40) is None


def test_token_carries_version() -> None:
    token = create_access_token("abc", token_version=3)
    claims = decode_access_token(token)
    assert claims[TOKEN_VERSION_CLAIM] == 3
    assert claims["sub"] == "abc"


def test_token_without_version_is_refused() -> None:
    settings = get_settings()
    bare = jwt.encode({"sub": "abc", "exp": int(time.time()) + 60}, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(ValueError):
        decode_access_token(bare)


def test_token_with_other_algorithm_is_refused() -> None:
    settings = get_settings()
    forged = jwt.encode(
        {"sub": "abc", "exp": int(time.time()) + 60, TOKEN_VERSION_CLAIM: 0},
        settings.jwt_secret,
        algorithm="HS512",
    )
    with pytest.raises(ValueError):
        decode_access_token(forged)


class FakeUser:
    def __init__(self, version: int, deleted: bool = False) -> None:
        self.tokenVersion = version
        self.deletedAt = object() if deleted else None
        self.sessionsValidFrom: datetime | None = None


def test_token_version_bump_ends_sessions() -> None:
    claims = decode_access_token(create_access_token("abc", token_version=1))
    assert token_matches_user(claims, FakeUser(1))
    assert not token_matches_user(claims, FakeUser(2))
    assert not token_matches_user(claims, FakeUser(1, deleted=True))


def _token_issued_at(monkeypatch: pytest.MonkeyPatch, moment: datetime) -> dict[str, object]:
    monkeypatch.setattr(security, "datetime", SimpleNamespace(now=lambda _zone: moment))
    return decode_access_token(create_access_token("abc", token_version=1))


def test_a_token_issued_after_sessions_end_in_the_same_second_is_live_and_one_before_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ended = datetime.now(UTC).replace(microsecond=500_000)
    user = FakeUser(1)
    user.sessionsValidFrom = ended
    assert token_matches_user(_token_issued_at(monkeypatch, ended + timedelta(milliseconds=23)), user)
    assert not token_matches_user(_token_issued_at(monkeypatch, ended - timedelta(milliseconds=100)), user)


def test_runtime_url_for_session_pooler() -> None:
    runtime = build_runtime_database_url(
        "postgresql://postgres.ref:pw@aws-1-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require&pgbouncer=true&connection_limit=5"
    )
    assert runtime.url.startswith("postgresql+psycopg://")
    assert "pgbouncer" not in runtime.url
    assert "connection_limit" not in runtime.url
    assert "sslmode=require" in runtime.url
    assert "application_name=kalavigyan-api" in runtime.url
    assert runtime.transaction_pooler


def test_runtime_url_transaction_pooler_disables_prepare() -> None:
    runtime = build_runtime_database_url(
        "postgresql://u:p@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"
    )
    assert runtime.transaction_pooler
    assert runtime.connect_args["prepare_threshold"] is None


def test_runtime_url_local() -> None:
    runtime = build_runtime_database_url("postgres://u:p@localhost:5432/db")
    assert runtime.url == "postgresql+psycopg://u:p@localhost:5432/db"
    assert not runtime.transaction_pooler


def test_sslmode_added_for_remote_hosts_only() -> None:
    assert "sslmode=require" in with_explicit_sslmode(
        "postgresql://u:p@db.example.supabase.co:5432/postgres", None
    )
    assert "sslmode" not in with_explicit_sslmode("postgresql://u:p@localhost:5432/db", None)


def test_redaction() -> None:
    text = "key sk-ant-api03-abcdefghijklmnop and AIzaSyA1234567890abcdefghij and Bearer abcdefghijklmnopqrstuvwx"
    redacted = redact_secrets(text)
    assert "abcdefghijklmnop" not in redacted
    assert "AIzaSyA1234567890" not in redacted
    assert "Bearer [redacted]" in redacted


def test_redaction_hides_keys_in_query_strings() -> None:
    line = "HTTP Request: GET https://api.example.org/works?q=dye&api_key=Zq81-secret&apiKey=Kq7 HTTP/1.1 200"
    assert redact_secrets(line) == (
        "HTTP Request: GET https://api.example.org/works?q=dye&api_key=[redacted]&apiKey=[redacted] HTTP/1.1 200"
    )


def test_hotp_rfc4226_vectors() -> None:
    key = b"12345678901234567890"
    expected = ["755224", "287082", "359152", "969429", "338314"]
    assert [two_factor.hotp(key, i) for i in range(5)] == expected


def test_totp_window_and_kinds() -> None:
    secret = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    now = 1_700_000_000.0
    code = two_factor.current_totp(secret, now)
    assert two_factor.match_totp_step(secret, code, now) == two_factor.time_step(now)
    assert two_factor.match_totp_step(secret, two_factor.current_totp(secret, now + 30), now) is not None
    assert two_factor.match_totp_step(secret, two_factor.current_totp(secret, now + 90), now) is None
    assert two_factor.code_kind("123 456") == two_factor.TOTP
    assert two_factor.code_kind("abcd-2345") == two_factor.RECOVERY
    assert two_factor.code_kind("12") is None
    assert two_factor.canonical_recovery_code("ABCD2345") == "abcd-2345"


def test_two_factor_secret_encryption_round_trip() -> None:
    sealed = two_factor.encrypt_secret("JBSWY3DPEHPK3PXP")
    assert sealed.startswith(two_factor.VERSIONED_PREFIX)
    assert two_factor.decrypt_secret(sealed) == "JBSWY3DPEHPK3PXP"
    tampered = sealed[:-2] + ("AA" if not sealed.endswith("AA") else "BB")
    assert two_factor.decrypt_secret(tampered) is None


def test_qr_svg_is_svg() -> None:
    svg = two_factor.qr_svg(two_factor.totp_uri("JBSWY3DPEHPK3PXP", "a@b.test"))
    assert svg.startswith("<svg") and svg.endswith("</svg>")


def test_google_claims_checks() -> None:
    now = 1_700_000_000
    base = {
        "aud": "cid",
        "iss": "https://accounts.google.com",
        "exp": now + 60,
        "email": "a@b.test",
        "email_verified": True,
        "nonce": "n",
    }
    assert google_auth.check_claims(base, "cid", now) is None
    assert google_auth.check_claims(base | {"aud": "other"}, "cid", now) == "audience"
    assert google_auth.check_claims(base | {"iss": "evil"}, "cid", now) == "issuer"
    assert google_auth.check_claims(base | {"exp": now - 1}, "cid", now) == "expired"
    assert google_auth.check_claims(base | {"email_verified": "true"}, "cid", now) == "email_unverified"
    missing = dict(base)
    del missing["nonce"]
    assert google_auth.check_claims(missing, "cid", now) == "nonce_missing"
    assert auth_nonces.nonce_hash("x") == auth_nonces.nonce_hash("x") != auth_nonces.nonce_hash("y")
