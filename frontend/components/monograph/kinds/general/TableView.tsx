"use client";

import { useId, useMemo } from "react";

import { GeneralFigure, UnitTable } from "@/components/monograph/kinds/general/GeneralFigure";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { parsedSpec, tableSpecShape } from "@/lib/componentSpecsGeneral";

export function TableView({ spec, renderUnit }: ComponentViewProps) {
  const table = useMemo(() => parsedSpec(tableSpecShape, spec), [spec]);
  const titleId = useId();
  if (!table) return null;
  const head = table.columns.map((column, at) => ({ key: `c${at}`, content: renderUnit(column.label), numeric: column.numeric }));
  const rows = table.rows.map((row, at) => ({
    key: `r${at}`,
    cells: row.cells.map((cell, column) => ({ key: `c${column}`, content: renderUnit(cell), numeric: table.columns[column]?.numeric }))
  }));
  return (
    <GeneralFigure kind="general_table" head={table.head} titleId={titleId} renderUnit={renderUnit}>
      <div className="overflow-x-auto">
        <UnitTable labelledBy={titleId} head={head} rows={rows} />
      </div>
    </GeneralFigure>
  );
}
