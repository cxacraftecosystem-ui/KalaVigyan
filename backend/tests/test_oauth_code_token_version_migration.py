from app.models import OAuthCode, OAuthGrant

from .migration_scripts import migration

STEP = migration("0101_oauth_code_token_version")
CREATED = migration("0037_oauth")


def test_it_follows_the_folded_chunk_acl() -> None:
    assert (STEP.revision, STEP.down_revision) == (
        "0101_oauth_code_token_version",
        "0100_signed_in_chunks_public",
    )


def test_it_adds_to_the_code_table_the_oauth_migration_made() -> None:
    assert STEP.TABLE == "OAuthCode" == OAuthCode.__tablename__
    assert STEP.TABLE in CREATED.TABLES
    assert STEP.COLUMN == "userTokenVersion"
    assert STEP.COLUMN in OAuthCode.__table__.columns and STEP.COLUMN in OAuthGrant.__table__.columns


def test_the_release_before_writes_a_code_without_the_new_column() -> None:
    column = OAuthCode.__table__.columns["userTokenVersion"]
    assert column.nullable is False
    assert column.server_default is not None and str(column.server_default.arg) == "0"
    assert STEP.RELEASE_BEFORE_VERSION == "0"
