from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DatasetTable, EnvDataset
from app.research.component_specs_general_delivery import CitedCell, cited_cells, cited_dataset
from app.research.quotes import numbers_in

__all__ = ["CellCheck", "checked_cells", "dataset_credit"]

NOT_HELD = "the dataset {code} holds no stored table: propose it with propose_dataset first"
NO_CELL = "the unit {unit} cites row {row}, column {column!r} of {code}, which its table does not hold"
NOT_STATED = "the value {value:g} of the unit {unit} is not the {stored!r} that row {row} of {code} states"


@dataclass(frozen=True)
class CellCheck:
    problems: list[str] = field(default_factory=list)
    rows: dict[str, list[str]] = field(default_factory=dict)
    dataset: dict[str, Any] | None = None


def dataset_credit(dataset: EnvDataset) -> dict[str, Any]:
    parts = [dataset.title, dataset.publisher, dataset.version]
    credit = ", ".join(part for part in parts if part) + f". {dataset.licence}."
    cite: dict[str, Any] = {"code": dataset.code, "credit": credit}
    url = dataset.landingUrl or dataset.url
    if url:
        cite["url"] = url
    return cite


async def checked_cells(session: AsyncSession, spec: Any) -> CellCheck:
    cite = cited_dataset(spec)
    if cite is None:
        return CellCheck()
    found = (
        await session.execute(
            select(EnvDataset, DatasetTable)
            .join(DatasetTable, DatasetTable.datasetId == EnvDataset.id)
            .where(EnvDataset.code == cite.code)
        )
    ).first()
    if found is None:
        return CellCheck(problems=[NOT_HELD.format(code=cite.code)])
    dataset, table = found
    check = CellCheck(dataset=dataset_credit(dataset))
    for cited in cited_cells(spec):
        _check_cell(check, cited, table, cite.code)
    return check


def _check_cell(check: CellCheck, cited: CitedCell, table: DatasetTable, code: str) -> None:
    stored = _stored(table, cited.cell.row, cited.cell.column)
    if stored is None:
        check.problems.append(
            NO_CELL.format(unit=cited.unit, row=cited.cell.row, column=cited.cell.column, code=code)
        )
        return
    if cited.value is not None and not _same(cited.value, numbers_in(stored)):
        check.problems.append(
            NOT_STATED.format(
                value=cited.value, unit=cited.unit, stored=stored, row=cited.cell.row, code=code
            )
        )
        return
    check.rows.setdefault(cited.unit, []).append(stored)


def _stored(table: DatasetTable, row: int, column: str) -> str | None:
    columns = list(table.columns)
    if column not in columns or not 1 <= row <= len(table.rows):
        return None
    values: Sequence[Any] = table.rows[row - 1]
    value = values[columns.index(column)]
    return value if isinstance(value, str) else None


def _same(value: float, figures: Sequence[str]) -> bool:
    for figure in figures:
        try:
            if float(figure) == value:
                return True
        except ValueError:
            continue
    return False
