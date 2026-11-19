"use client";

import { AnswerFigure } from "@/components/answer/place/AnswerFigure";
import { RainfallBars, RainfallCredit, rainTable } from "@/components/answer/place/RainfallBars";
import { MONTH_GRID, MonthHeader, StripLine } from "@/components/answer/place/StripLine";
import { CitedText } from "@/components/answer/ProseBlockView";
import type { Season, SeasonRow, SeasonsBlock } from "@/lib/explainerPlace";
import { datasetRow } from "@/lib/placeView";
import { MONTHS, monthsText, rainfallFinding, SEASON_LABEL } from "@/lib/seasonsView";
import { cn } from "@/lib/utils";

const MONTH_MARK = { color: "var(--chart-series)" };

function SeasonChip({ season }: { season: Season }) {
  return (
    <span className="kv-tag w-fit" data-testid="season-chip">
      {SEASON_LABEL[season]}
    </span>
  );
}

function MonthCells({ months }: { months: readonly number[] }) {
  const named = new Set(months);
  return (
    <>
      <div aria-hidden className={MONTH_GRID} data-testid="month-cells" style={MONTH_MARK}>
        {MONTHS.map((month) => (
          <span key={month} data-on={named.has(month) ? "true" : "false"} className={cn("h-3", named.has(month) ? "bg-current" : "bg-sunk")} />
        ))}
      </div>
      <span className="sr-only">{monthsText(months)}</span>
    </>
  );
}

function RowLabel({ row }: { row: SeasonRow }) {
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <span className="min-w-0 break-words font-ui text-label font-semibold text-ink-1">{row.label}</span>
      {row.season && row.months.length > 0 ? <SeasonChip season={row.season} /> : null}
    </div>
  );
}

function SeasonRowView({ row }: { row: SeasonRow }) {
  return (
    <li className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-1.5 border-t border-rule pt-3" data-testid="season-row">
      <StripLine label={<RowLabel row={row} />}>
        {row.months.length > 0 ? <MonthCells months={row.months} /> : row.season ? <SeasonChip season={row.season} /> : null}
      </StripLine>
      <StripLine label={null}>
        <CitedText id={row.sentence.id} sentences={[row.sentence]} className="max-w-measure font-reading text-body-sm text-ink-1" />
      </StripLine>
    </li>
  );
}

export function SeasonsStrip({ block }: { block: SeasonsBlock }) {
  const rain = block.rainfall;
  const monthly = rain !== null || block.rows.some((row) => row.months.length > 0);
  const texts = rain ? { title: rainfallFinding(rain), source: <RainfallCredit rain={rain} dataset={datasetRow(block.datasets, rain.datasetCode)} /> } : {};
  return (
    <AnswerFigure texts={texts} table={rain ? rainTable(rain) : null} data-testid="seasons-strip">
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3">
        {rain ? <RainfallBars rain={rain} /> : null}
        {monthly ? <MonthHeader /> : null}
        <ol className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3">
          {block.rows.map((row) => (
            <SeasonRowView key={row.sentence.id} row={row} />
          ))}
        </ol>
      </div>
    </AnswerFigure>
  );
}
