import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.sql.sqltypes import Enum

from app.models import Base
from app.models.base import pg_enum

from .db.previous_release_probe import (
    RETIRED_TABLES,
    engine_url,
    labels_it_refuses,
    probed_tables,
    reads_later_labels,
    trigger_filled,
    unwritable_columns,
)

LISTED = ("OPENAI", "GEMINI")


def read(kind: Enum, value: str) -> object:
    processor = kind.result_processor(postgresql.dialect(), None)
    assert processor is not None
    return processor(value)


def test_a_table_this_release_retired_is_left_unread_once_dropped_and_no_other_is() -> None:
    mapped = ["CraftPage", "CraftPageArchive", "CraftPageSnapshot"]
    assert probed_tables(mapped, ["CraftPage", "CraftPageSnapshot"]) == ["CraftPage", "CraftPageSnapshot"]
    assert probed_tables(mapped, mapped) == mapped
    assert probed_tables(mapped, ["CraftPageArchive"]) == mapped
    assert {"CraftPageArchive"} == RETIRED_TABLES
    assert "CraftPageArchive" not in {mapper.local_table.name for mapper in Base.registry.mappers}


def test_a_label_a_later_release_adds_is_read_as_its_own_text() -> None:
    kind = pg_enum("AiProvider", LISTED)
    assert (read(kind, "GEMINI"), read(kind, "VOYAGE")) == ("GEMINI", "VOYAGE")
    assert reads_later_labels(kind)
    assert labels_it_refuses(kind, ["OPENAI", "VOYAGE", "RERANK"]) == []


def test_a_closed_enum_refuses_it_as_the_admin_route_save_did_on_2026_11_22() -> None:
    closed = ENUM(*LISTED, name="AiProvider", create_type=False)
    with pytest.raises(LookupError, match="VOYAGE"):
        read(closed, "VOYAGE")
    assert not reads_later_labels(closed)
    assert labels_it_refuses(closed, ["OPENAI", "VOYAGE", "RERANK"]) == ["RERANK", "VOYAGE"]


def test_every_enum_column_of_this_release_reads_a_label_a_later_release_adds() -> None:
    closed = [
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, Enum) and not reads_later_labels(column.type)
    ]
    assert closed == []


def test_a_required_column_the_release_before_does_not_map_makes_its_writes_fail() -> None:
    stored = [
        {"name": "id", "nullable": False, "default": "gen_random_uuid()"},
        {"name": "name", "nullable": False, "default": None},
        {"name": "weight", "nullable": False, "default": None},
        {"name": "note", "nullable": True, "default": None},
        {"name": "rank", "nullable": False, "default": None, "identity": {"start": 1}},
        {"name": "words", "nullable": False, "default": None, "computed": {"sqltext": "to_tsvector(name)"}},
    ]
    assert unwritable_columns(["id", "name"], stored) == ["weight"]
    assert unwritable_columns(["id"], stored, filled={"name", "weight"}) == []


def test_a_column_a_before_insert_trigger_assigns_is_filled_for_the_release_before() -> None:
    source = (
        'BEGIN IF NEW."clientName" IS NULL THEN SELECT k."name" INTO NEW."clientName" FROM x; END IF; END'
    )
    assert trigger_filled([source], ["clientName", "tool", "name"]) == {"clientName"}
    assert trigger_filled([], ["clientName"]) == set()


def test_the_probe_reaches_postgres_through_psycopg() -> None:
    assert engine_url("postgresql://u:p@localhost:5432/kv") == "postgresql+psycopg://u:p@localhost:5432/kv"
    assert engine_url("postgres://u:p@h/kv") == "postgresql+psycopg://u:p@h/kv"
    assert engine_url("postgresql+psycopg://u:p@h/kv") == "postgresql+psycopg://u:p@h/kv"
