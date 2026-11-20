from sqlalchemy import CheckConstraint, Integer, String

from app.models import AllowanceBucket

from .migration_scripts import migration


def test_the_shared_allowances_follow_the_drafts_and_supplied_sources() -> None:
    step = migration("0053_shared_allowances")
    assert (step.revision, step.down_revision) == (
        "0053_shared_allowances",
        "0052_drafts_and_supplied_sources",
    )


def test_the_bucket_table_is_written_as_the_model_holds_it() -> None:
    step = migration("0053_shared_allowances")
    table = AllowanceBucket.__table__
    assert step.TABLE == AllowanceBucket.__tablename__ == "AllowanceBucket"
    assert [column.name for column in table.primary_key.columns] == ["holder", "kind", "hourStart"]
    assert set(table.c.keys()) == {"holder", "kind", "hourStart", "used", "lastTaken"}
    assert isinstance(table.c.holder.type, String) and table.c.holder.type.length == step.HOLDER_CHARS == 80
    assert isinstance(table.c.kind.type, String) and table.c.kind.type.length == step.KIND_CHARS == 40
    assert isinstance(table.c.used.type, Integer) and isinstance(table.c.lastTaken.type, Integer)
    checks = {str(item.sqltext) for item in table.constraints if isinstance(item, CheckConstraint)}
    assert checks == {'"used" >= 0', step.LAST_TAKEN}
