import importlib
import json
import os
import sys
from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import Engine, Table, create_engine, inspect, select, text
from sqlalchemy.engine import Inspector
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapper, Session
from sqlalchemy.sql.sqltypes import Enum

LATER_LABEL = "A_LABEL_A_LATER_RELEASE_ADDS"
DRIVER = "postgresql+psycopg"
ENUM_LABELS = text("SELECT t.typname, e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid")
ROW_BEFORE_INSERT = 7
INSERT_TRIGGERS = text(
    "SELECT p.prosrc FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid "
    "WHERE t.tgrelid = to_regclass(:table) AND NOT t.tgisinternal AND t.tgtype & :kind = :kind"
)


def reads_later_labels(kind: Enum) -> bool:
    try:
        return kind._object_value_for_elem(LATER_LABEL) == LATER_LABEL
    except LookupError:
        return False


def labels_it_refuses(kind: Enum, stored: Iterable[str]) -> list[str]:
    if reads_later_labels(kind):
        return []
    return sorted(set(stored) - set(kind.enums))


def needs_a_value(column: Mapping[str, Any]) -> bool:
    filled = column.get("default") is not None or column.get("identity") or column.get("computed")
    return not column["nullable"] and not filled


def trigger_filled(sources: Iterable[str], columns: Iterable[str]) -> set[str]:
    return {column for column in columns if any(f'NEW."{column}"' in source for source in sources)}


def unwritable_columns(
    mapped: Iterable[str], stored: Iterable[Mapping[str, Any]], *, filled: Iterable[str] = ()
) -> list[str]:
    known = set(mapped) | set(filled)
    return sorted(
        column["name"] for column in stored if needs_a_value(column) and column["name"] not in known
    )


def engine_url(url: str) -> str:
    scheme, rest = url.split("://", 1)
    return f"{DRIVER}://{rest}" if scheme in {"postgres", "postgresql"} else url


def probe(engine: Engine, mappers: Iterable[Mapper[Any]]) -> dict[str, Any]:
    labels = _stored_labels(engine)
    schema = inspect(engine)
    report: dict[str, Any] = {"tables": 0, "unreadable": [], "refusedLabels": [], "unwritable": []}
    for mapper in sorted(mappers, key=lambda found: _table(found).name):
        table = _table(mapper)
        report["tables"] += 1
        report["unreadable"] += _unreadable(engine, mapper)
        report["refusedLabels"] += _refused(table, labels)
        report["unwritable"] += _unwritable(engine, schema, table)
    return report


def _table(mapper: Mapper[Any]) -> Table:
    table = mapper.local_table
    if not isinstance(table, Table):
        raise TypeError(f"{mapper.class_.__name__} maps {table!r}, not a table")
    return table


def _stored_labels(engine: Engine) -> Mapping[str, list[str]]:
    found: dict[str, list[str]] = {}
    with engine.connect() as connection:
        for name, label in connection.execute(ENUM_LABELS):
            found.setdefault(name, []).append(label)
    return found


def _unreadable(engine: Engine, mapper: Mapper[Any]) -> list[str]:
    try:
        with Session(engine) as session:
            session.scalars(select(mapper.class_)).all()
    except (SQLAlchemyError, LookupError, ValueError) as error:
        return [f"{_table(mapper).name}: {type(error).__name__}: {str(error).splitlines()[0]}"]
    return []


def _refused(table: Table, labels: Mapping[str, list[str]]) -> list[str]:
    found: list[str] = []
    for column in table.columns:
        kind = column.type
        if isinstance(kind, Enum) and kind.name:
            found += [
                f"{table.name}.{column.name}: {label}"
                for label in labels_it_refuses(kind, labels.get(kind.name, []))
            ]
    return found


def _unwritable(engine: Engine, schema: Inspector, table: Table) -> list[str]:
    if not schema.has_table(table.name):
        return []
    stored = schema.get_columns(table.name)
    with engine.connect() as connection:
        sources = connection.scalars(INSERT_TRIGGERS, {"table": f'"{table.name}"', "kind": ROW_BEFORE_INSERT})
        filled = trigger_filled(list(sources), [column["name"] for column in stored])
    mapped = [column.name for column in table.columns]
    return [f"{table.name}.{name}" for name in unwritable_columns(mapped, stored, filled=filled)]


def main() -> int:
    importlib.import_module("app.models")
    base = importlib.import_module("app.models.base")
    engine = create_engine(engine_url(os.environ["DATABASE_URL"]))
    try:
        print(json.dumps(probe(engine, base.Base.registry.mappers)))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
