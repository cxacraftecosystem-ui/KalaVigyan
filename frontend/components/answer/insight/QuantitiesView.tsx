"use client";

import { CitedText } from "@/components/answer/ProseBlockView";
import type { QuantitiesBlock, QuantityRow } from "@/lib/explainerInsight";
import { AMOUNT_KIND_LABEL } from "@/lib/insightView";
import { bySentence, type SentenceGroup } from "@/lib/sentenceGroups";
import { cn } from "@/lib/utils";

const HEAD = "px-2 py-2 text-start font-ui text-label font-normal text-ink-2";
const CELL = "px-2 pt-2 align-baseline";

function QuantityGroup({ group }: { group: SentenceGroup<QuantityRow> }) {
  return (
    <tbody className="border-b border-rule" data-testid="quantity-sentence">
      {group.items.map((row, index) => (
        <tr key={`${index}-${row.stated}`} data-testid="quantity-row" data-measures={row.measures}>
          <th scope="row" className={cn(CELL, "text-start font-ui text-label font-normal text-ink-2")}>
            {AMOUNT_KIND_LABEL[row.measures]}
          </th>
          <td className={cn(CELL, "break-words font-ui text-ui font-semibold text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]")} data-testid="quantity-stated">
            {row.stated}
          </td>
        </tr>
      ))}
      <tr>
        <td colSpan={2} className="px-2 pb-3 pt-1.5">
          <CitedText id={group.sentence.id} sentences={[group.sentence]} className="max-w-measure font-reading text-body-sm text-ink-1" />
        </td>
      </tr>
    </tbody>
  );
}

export function QuantitiesView({ block }: { block: QuantitiesBlock }) {
  return (
    <table className="w-full min-w-0 border-collapse" data-testid="quantities">
      <caption className="kicker pb-2 text-start">Stated quantities</caption>
      <thead>
        <tr className="border-b border-ink-1">
          <th scope="col" className={HEAD}>
            Measure
          </th>
          <th scope="col" className={HEAD}>
            As stated
          </th>
        </tr>
      </thead>
      {bySentence(block.rows, (row) => row.sentence).map((group) => (
        <QuantityGroup key={group.key} group={group} />
      ))}
    </table>
  );
}
