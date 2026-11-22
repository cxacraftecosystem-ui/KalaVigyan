"use client";

import { ArrowRight } from "lucide-react";

import { CitationChips } from "@/components/answer/CitationContext";
import { CitedText } from "@/components/answer/ProseBlockView";
import { DatasetCredit } from "@/components/DatasetCredit";
import type { MeasureBlock, MeasureRow } from "@/lib/explainerInsight";
import { basisText, factorText, measureDatasets, metricText } from "@/lib/insightView";
import { bySentence, type SentenceGroup } from "@/lib/sentenceGroups";

function Conversion({ row }: { row: MeasureRow }) {
  const conversion = row.conversion;
  return (
    <p className="font-ui text-label font-normal text-ink-3" data-testid="measure-basis" data-basis={conversion.basis}>
      <span className="font-semibold text-ink-2 [font-variant-numeric:lining-nums_tabular-nums]">{factorText(conversion)}</span>
      <span> · {basisText(conversion)}</span>
      {conversion.citation ? <CitationChips citations={[conversion.citation]} /> : null}
    </p>
  );
}

function MeasureRowView({ row }: { row: MeasureRow }) {
  return (
    <li className="grid min-w-0 content-start gap-1" data-testid="measure-row">
      <p className="flex min-w-0 flex-wrap items-baseline gap-x-2.5 gap-y-1 font-reading text-h3 text-ink-1">
        <span className="min-w-0 break-words" data-testid="measure-stated">
          {row.stated}
        </span>
        <ArrowRight className="h-4 w-4 shrink-0 self-center text-ink-3 rtl:-scale-x-100" aria-hidden />
        <span className="sr-only">is</span>
        <span className="min-w-0 break-words [font-variant-numeric:lining-nums_tabular-nums]" data-testid="measure-metric">
          {metricText(row)}
        </span>
      </p>
      <Conversion row={row} />
    </li>
  );
}

function MeasureSentenceView({ group }: { group: SentenceGroup<MeasureRow> }) {
  return (
    <li className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-2 border-b border-rule py-3 md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)] md:gap-x-8" data-testid="measure-sentence">
      <ul className="grid min-w-0 content-start gap-3">
        {group.items.map((row, index) => (
          <MeasureRowView key={`${index}-${row.stated}`} row={row} />
        ))}
      </ul>
      <CitedText id={group.sentence.id} sentences={[group.sentence]} className="max-w-measure font-reading text-body-sm text-ink-1" />
    </li>
  );
}

export function MeasureView({ block }: { block: MeasureBlock }) {
  const datasets = measureDatasets(block.rows);
  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3" data-testid="measure">
      <ul className="grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-ink-1">
        {bySentence(block.rows, (row) => row.sentence).map((group) => (
          <MeasureSentenceView key={group.key} group={group} />
        ))}
      </ul>
      {datasets.length > 0 ? (
        <div className="grid min-w-0 gap-2">
          {datasets.map((dataset) => (
            <DatasetCredit key={dataset.code} dataset={dataset} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
