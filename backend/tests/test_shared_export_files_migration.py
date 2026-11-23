from app.models import SharedExportFile
from app.models.sharing import OBJECT_KEY_CHARS, SHARE_TOKEN_CHARS

from .migration_scripts import migration

STEP = migration("0079_shared_export_files")


def test_it_follows_the_head_of_round_7s_chain() -> None:
    assert (STEP.revision, STEP.down_revision) == ("0079_shared_export_files", "0072_quantities_kind")


def test_it_creates_the_table_the_model_holds() -> None:
    table = SharedExportFile.__table__
    assert STEP.FILES == table.name == "SharedExportFile"
    assert [column.name for column in table.primary_key.columns] == ["key"]
    assert STEP.OBJECT_KEY_CHARS == OBJECT_KEY_CHARS == table.c["key"].type.length == 1024
    assert STEP.SHARE_TOKEN_CHARS == SHARE_TOKEN_CHARS == table.c["shareToken"].type.length == 64
    assert not table.c["shareToken"].nullable
    assert [tuple(index.columns.keys()) for index in table.indexes] == [("shareToken",)]
