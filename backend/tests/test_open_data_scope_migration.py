from sqlalchemy import Index, UniqueConstraint

from app.models import OpenDataRelease
from app.models.open_data import SCOPE_CHARS

from .migration_scripts import migration

STEP = migration("0062_open_data_scope")


def test_it_follows_the_embedding_recipe_migration() -> None:
    assert (STEP.revision, STEP.down_revision) == ("0062_open_data_scope", "0061_embedding_recipe")


def test_it_adds_the_scope_the_model_holds_and_keys_versions_by_target_and_scope() -> None:
    column = OpenDataRelease.__table__.c["scope"]
    assert column.nullable and STEP.SCOPE_CHARS == SCOPE_CHARS == column.type.length
    uniques = [c for c in OpenDataRelease.__table__.constraints if isinstance(c, UniqueConstraint)]
    assert [tuple(c.columns.keys()) for c in uniques] == [STEP.UNIQUE_AFTER]
    assert uniques[0].dialect_options["postgresql"]["nulls_not_distinct"] is True
    indexes = [
        tuple(index.columns.keys()) for index in OpenDataRelease.__table__.indexes if isinstance(index, Index)
    ]
    assert indexes == [STEP.INDEX_AFTER]
    assert STEP.UNIQUE_BEFORE == ("target", "version")
    assert STEP._name(STEP.UNIQUE_AFTER, "key") == "OpenDataRelease_target_scope_version_key"
    assert STEP._name(STEP.INDEX_AFTER, "idx") == "OpenDataRelease_target_scope_state_releasedOn_idx"
