from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = ["Column", "ColumnType", "Table", "col"]

ColumnType = Literal["string", "integer", "number", "boolean", "date", "datetime", "array", "object"]


@dataclass(frozen=True)
class Column:
    name: str
    type: ColumnType
    description: str
    required: bool = False


@dataclass(frozen=True)
class Table:
    name: str
    title: str
    description: str
    key: tuple[str, ...]
    columns: tuple[Column, ...]

    def names(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)


def col(name: str, kind: ColumnType, description: str, *, required: bool = False) -> Column:
    return Column(name=name, type=kind, description=description, required=required)
