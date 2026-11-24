from app.models import OAuthCode

from .migration_scripts import migration

STEP = migration("0101_oauth_code_token_version")


def test_it_follows_the_folded_chunk_acl() -> None:
    assert (STEP.revision, STEP.down_revision) == (
        "0101_oauth_code_token_version",
        "0100_signed_in_chunks_public",
    )


def test_the_release_before_writes_a_code_without_the_new_column() -> None:
    column = OAuthCode.__table__.columns["userTokenVersion"]
    assert column.nullable is False
    assert column.server_default is not None and str(column.server_default.arg) == "0"
