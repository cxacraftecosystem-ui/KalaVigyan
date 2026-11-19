"use client";

import Link from "next/link";

import { READING_PROSE } from "@/components/answer/place/figureMarks";
import { CitedText } from "@/components/answer/ProseBlockView";
import type { CraftLink } from "@/lib/answerShapes";
import { compareLayout, rowTitle, type CompareLayout } from "@/lib/compareView";
import type { CompareBlock, CompareCell, CompareRow } from "@/lib/explainerLearning";
import { listText } from "@/lib/format";
import { cn } from "@/lib/utils";

function HeadRow({ crafts, layout }: { crafts: readonly CraftLink[]; layout: CompareLayout }) {
  return (
    <div role="row" className={cn("min-w-0", layout.head)} data-testid="compare-head">
      <span role="columnheader" className="min-w-0">
        <span className="sr-only">Aspect</span>
      </span>
      {crafts.map((craft) => (
        <span key={craft.slug} role="columnheader" className="min-w-0">
          <Link href={craft.path} className="kv-link min-w-0 break-words font-ui text-h4">
            {craft.name}
          </Link>
        </span>
      ))}
    </div>
  );
}

function Cell({ cell, craft, layout }: { cell: CompareCell | null; craft: CraftLink; layout: CompareLayout }) {
  return (
    <div role="cell" className={layout.cell} data-testid="compare-cell" data-filled={cell ? "true" : "false"}>
      <span className={cn("font-ui text-caption font-semibold text-ink-3", layout.cellName)}>{craft.name}</span>
      {cell ? (
        <CitedText id={cell.sentence.id} sentences={[cell.sentence]} className={READING_PROSE} />
      ) : (
        <span className="font-ui text-ui text-ink-3">
          <span aria-hidden>—</span>
          <span className="sr-only">Not stated</span>
        </span>
      )}
    </div>
  );
}

function Row({ row, crafts, layout }: { row: CompareRow; crafts: readonly CraftLink[]; layout: CompareLayout }) {
  const title = rowTitle(row);
  return (
    <div role="row" className={layout.row} data-testid="compare-row">
      <div role="rowheader" className="grid min-w-0 content-start gap-0.5">
        {title.facet ? <span className="kicker">{title.facet}</span> : null}
        <span className="break-words font-ui text-h4 text-ink-1">{title.title}</span>
      </div>
      {crafts.map((craft, index) => (
        <Cell key={craft.slug} cell={row.cells[index] ?? null} craft={craft} layout={layout} />
      ))}
    </div>
  );
}

export function CompareTable({ block }: { block: CompareBlock }) {
  const layout = compareLayout(block.crafts.length);
  const names = listText(block.crafts.map((craft) => craft.name));
  return (
    <div role="table" aria-label={`${names} compared`} className="grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-ink-1 pt-3" data-testid="compare" data-crafts={block.crafts.length}>
      <HeadRow crafts={block.crafts} layout={layout} />
      {block.rows.map((row) => (
        <Row key={`${row.facet}-${row.term?.key ?? ""}`} row={row} crafts={block.crafts} layout={layout} />
      ))}
    </div>
  );
}
