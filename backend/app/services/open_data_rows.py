from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from .open_data_catalogue import component_rows, dataset_rows
from .open_data_claims import published_facts
from .open_data_crafts import category_rows, craft_lookup, craft_place_rows, craft_rows, family_rows
from .open_data_schema import Table
from .open_data_structure import curated_structure
from .open_data_tables import TABLES, TABLES_BY_NAME
from .open_data_values import Row

__all__ = ["OpenDataTables", "checked_tables", "read_tables", "row_key"]

KEY_SEPARATOR = "|"
WRONG_COLUMNS = "A {table} row holds {found}, not the columns {expected}."
REPEATED_KEY = "Two {table} rows share the key {key}."
WRONG_TABLES = "The release holds the tables {found}, not {expected}."


@dataclass(frozen=True)
class OpenDataTables:
    rows: Mapping[str, list[Row]]

    def counts(self) -> dict[str, int]:
        return {table.name: len(self.rows[table.name]) for table in TABLES}

    def of(self, table: Table) -> list[Row]:
        return self.rows[table.name]


async def read_tables(session: AsyncSession, *, site: str) -> OpenDataTables:
    lookup = await craft_lookup(session)
    facts = await published_facts(session, lookup)
    shown = facts.claim_ids()
    structure = await curated_structure(session, lookup, shown)
    return checked_tables(
        {
            "claims": facts.claims,
            "citations": facts.citations,
            "sources": facts.sources,
            "crafts": await craft_rows(session, lookup, site=site),
            "craft_places": await craft_place_rows(session, lookup),
            "categories": await category_rows(session, lookup, site=site),
            "families": family_rows(lookup),
            "stages": structure.stages,
            "materials": structure.materials,
            "reactions": structure.reactions,
            "native_names": structure.native_names,
            "gi_records": structure.gi_records,
            "components": await component_rows(session, shown),
            "datasets": await dataset_rows(session),
        }
    )


def checked_tables(rows: Mapping[str, list[Row]]) -> OpenDataTables:
    expected = [table.name for table in TABLES]
    if sorted(rows) != sorted(expected):
        raise ValueError(WRONG_TABLES.format(found=sorted(rows), expected=sorted(expected)))
    for name in expected:
        _check_rows(TABLES_BY_NAME[name], rows[name])
    return OpenDataTables(rows={name: list(rows[name]) for name in expected})


def row_key(table: Table, row: Row) -> str:
    return KEY_SEPARATOR.join("" if row[name] is None else str(row[name]) for name in table.key)


def _check_rows(table: Table, rows: list[Row]) -> None:
    columns = table.names()
    seen: set[str] = set()
    for row in rows:
        if tuple(row) != columns:
            raise ValueError(WRONG_COLUMNS.format(table=table.name, found=list(row), expected=list(columns)))
        key = row_key(table, row)
        if key in seen:
            raise ValueError(REPEATED_KEY.format(table=table.name, key=key))
        seen.add(key)
