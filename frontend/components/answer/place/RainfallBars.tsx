"use client";

import { useRef, useState, type KeyboardEvent } from "react";

import type { FigureTable } from "@/components/answer/place/AnswerFigure";
import { MONTH_GRID, StripLine } from "@/components/answer/place/StripLine";
import { DataTable } from "@/components/charts/DataTable";
import { DatasetCredit } from "@/components/DatasetCredit";
import type { MonthlyRain } from "@/lib/explainerPlace";
import type { RegionDataset } from "@/lib/regionContract";
import { MONTH_NAMES, MONTHS, monthReading, rainShares, rainText, wettestMonth } from "@/lib/seasonsView";
import { cn } from "@/lib/utils";

const STEP: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
const RAIN_SERIES = { color: "var(--series-rain)" };
const RAIN_EMPH = { color: "var(--chart-emph)" };
const COLUMNS = [
  { key: "month", label: "Month" },
  { key: "rain", label: "Rainfall, monthly normal", numeric: true }
];

function shifted(month: number, by: number): number {
  return ((month - 1 + by + MONTHS.length) % MONTHS.length) + 1;
}

function edgeMonth(key: string, month: number): number | null {
  if (key === "Home") return 1;
  if (key === "End") return MONTHS.length;
  const by = STEP[key];
  return by === undefined ? null : shifted(month, by);
}

export function rainTable(rain: MonthlyRain): FigureTable {
  const rows = MONTHS.map((month) => ({ key: String(month), cells: { month: MONTH_NAMES[month - 1], rain: rainText(rain.millimetres[month - 1]) } }));
  return { node: <DataTable caption={`Rainfall in ${rain.district.name}, ${rain.district.stateName}, by month`} columns={COLUMNS} rows={rows} />, count: rows.length };
}

export function RainfallBars({ rain }: { rain: MonthlyRain }) {
  const wettest = wettestMonth(rain);
  const [active, setActive] = useState(wettest);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const shares = rainShares(rain);

  const move = (event: KeyboardEvent<HTMLButtonElement>, month: number) => {
    const next = edgeMonth(event.key, month);
    if (next === null) return;
    event.preventDefault();
    setActive(next);
    buttons.current[next - 1]?.focus();
  };

  return (
    <div className="min-w-0" data-testid="rainfall-bars">
      <StripLine label={<span className="font-ui text-label text-ink-2">Rainfall</span>}>
        <p className="mb-1.5 font-ui text-label text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]" data-testid="rainfall-reading">
          {active === wettest ? <span className="font-normal text-ink-3">Wettest · </span> : null}
          {monthReading(rain, active)}
        </p>
        <div role="group" aria-label="Monthly rainfall" className={cn(MONTH_GRID, "h-24 items-end border-b border-ink-1")}>
          {MONTHS.map((month) => (
            <button
              key={month}
              ref={(node) => {
                buttons.current[month - 1] = node;
              }}
              type="button"
              tabIndex={month === active ? 0 : -1}
              aria-label={monthReading(rain, month)}
              onPointerEnter={() => setActive(month)}
              onFocus={() => setActive(month)}
              onClick={() => setActive(month)}
              onKeyDown={(event) => move(event, month)}
              className={cn("flex h-full min-w-0 items-end", month === active ? "bg-sunk" : null)}
              style={month === wettest ? RAIN_EMPH : RAIN_SERIES}
              data-month={month}
            >
              <span className="block w-full bg-current" style={{ height: `${(shares[month - 1] * 100).toFixed(2)}%` }} />
            </button>
          ))}
        </div>
      </StripLine>
    </div>
  );
}

export function RainfallCredit({ rain, dataset }: { rain: MonthlyRain; dataset: RegionDataset | null }) {
  return (
    <span className="grid gap-1" data-testid="rainfall-credit">
      <span>
        Rainfall · {rain.district.name}, {rain.district.stateName} · monthly normal · {rain.period}
      </span>
      {dataset ? <DatasetCredit dataset={dataset} /> : null}
    </span>
  );
}
