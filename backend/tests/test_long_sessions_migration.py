from app.models import SiteSession

from .migration_scripts import migration

STEP = migration("0126_long_sessions")


def test_the_site_session_table_follows_the_section_proposals() -> None:
    assert (STEP.revision, STEP.down_revision) == ("0126_long_sessions", "0125_section_proposals")


def test_the_migration_creates_the_table_the_model_maps() -> None:
    assert STEP.TABLE == "SiteSession" == SiteSession.__tablename__
    assert {column.name for column in SiteSession.__table__.columns} == {
        "id",
        "userId",
        "createdAt",
        "renewedAt",
        "endedAt",
    }
    assert SiteSession.__table__.c["endedAt"].nullable is True
    assert SiteSession.__table__.c["renewedAt"].nullable is False
