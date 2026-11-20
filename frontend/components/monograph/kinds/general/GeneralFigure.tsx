import type { ReactNode } from "react";

import { GENERAL_KICKERS, type GeneralHead, type GeneralKind } from "@/lib/componentSpecsGeneral";

export type RenderUnit = (ref: string) => ReactNode;

type FigureProps = {
  kind: GeneralKind;
  head: GeneralHead;
  titleId: string;
  renderUnit: RenderUnit;
  values?: { count: number; table: ReactNode };
  children: ReactNode;
};

export function GeneralFigure({ kind, head, titleId, renderUnit, values, children }: FigureProps) {
  return (
    <figure className="kv-figure grid gap-3.5" data-general={kind} data-testid="general-figure">
      <figcaption className="grid gap-1.5">
        <p className="kv-fig-no">{GENERAL_KICKERS[kind]}</p>
        <p id={titleId} className="max-w-measure font-reading text-h3 text-ink-1 [font-variant-numeric:lining-nums]">
          {renderUnit(head.title)}
        </p>
        {head.caption ? <p className="max-w-measure font-reading text-body-sm text-ink-2">{renderUnit(head.caption)}</p> : null}
      </figcaption>
      <div className="min-w-0">{children}</div>
      {values ? (
        <details className="min-w-0">
          <summary className="kv-link inline-flex min-h-target cursor-pointer items-center font-ui text-ui">{`All ${values.count} values`}</summary>
          <div className="overflow-x-auto pt-2">{values.table}</div>
        </details>
      ) : null}
    </figure>
  );
}

export type TableCell = { key: string; content: ReactNode; numeric?: boolean };

export function UnitTable({ labelledBy, head, rows }: { labelledBy: string; head: TableCell[]; rows: { key: string; cells: TableCell[] }[] }) {
  return (
    <table aria-labelledby={labelledBy} className="w-full border-collapse font-ui text-ui font-normal text-ink-1" data-testid="general-table">
      <thead>
        <tr className="border-b border-ink-1">
          {head.map((cell) => (
            <th key={cell.key} scope="col" className={cellClass(cell, "py-2 text-label text-ink-2")}>
              {cell.content}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key} className="border-b border-rule">
            {row.cells.map((cell, at) =>
              at === 0 ? (
                <th key={cell.key} scope="row" className={cellClass(cell, "py-1.5 font-normal")}>
                  {cell.content}
                </th>
              ) : (
                <td key={cell.key} className={cellClass(cell, "py-1.5")}>
                  {cell.content}
                </td>
              )
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function cellClass(cell: TableCell, base: string): string {
  const aligned = cell.numeric ? "text-end [font-variant-numeric:lining-nums_tabular-nums]" : "text-start";
  return `px-2 align-top ${base} ${aligned}`;
}
