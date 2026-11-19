"use client";

import { TrendChart } from "@/components/answer/insight/TrendChart";
import { TrendSeries } from "@/components/answer/insight/TrendSeries";
import { CitedText } from "@/components/answer/ProseBlockView";
import { DatasetCredit } from "@/components/DatasetCredit";
import { matchingTrend, seriesPoints } from "@/lib/climateSeries";
import { groundwaterLabel, groundwaterReading, trendGroups } from "@/lib/climateView";
import type { ClimateRiskBlock, ClimateSeries, GroundwaterValue } from "@/lib/explainerInsight";

function Groundwater({ values }: { values: readonly GroundwaterValue[] }) {
  return (
    <section className="grid min-w-0 gap-2" aria-label="Groundwater" data-testid="groundwater">
      <h4 className="kicker">Groundwater</h4>
      <dl className="grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-ink-1 sm:grid-cols-[repeat(2,minmax(0,1fr))] sm:gap-x-8">
        {values.map((value) => (
          <div key={`${value.district.districtLgd}-${value.datasetCode}-${value.variable}`} className="grid min-w-0 gap-0.5 border-b border-rule py-3" data-testid="groundwater-value">
            <dt className="font-ui text-label text-ink-2">
              {groundwaterLabel(value)} · {value.district.name}
            </dt>
            <dd className="break-words font-ui text-ui-lg font-semibold text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]">{groundwaterReading(value)}</dd>
            <dd className="font-ui text-caption text-ink-3">{[value.period, value.resolution].join(" · ")}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function drawnSeries(block: ClimateRiskBlock): ClimateSeries[] {
  return (block.series ?? []).filter((series) => seriesPoints(series).length > 1);
}

function SeriesCharts({ block }: { block: ClimateRiskBlock }) {
  const series = drawnSeries(block);
  if (series.length === 0) return null;
  return (
    <div className={series.length > 1 ? "grid min-w-0 grid-cols-[minmax(0,1fr)] gap-6 md:grid-cols-[repeat(2,minmax(0,1fr))]" : "min-w-0"}>
      {series.map((entry) => (
        <TrendSeries key={`${entry.district.districtLgd}-${entry.variable}-${entry.datasetCode}`} series={entry} trend={matchingTrend(entry, block.trends)} />
      ))}
    </div>
  );
}

export function ClimateRiskView({ block }: { block: ClimateRiskBlock; reduce?: boolean }) {
  const groups = trendGroups(block.trends);
  if (groups.length === 0 && block.groundwater.length === 0) return null;
  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-6" data-testid="climate-risk">
      {groups.map((group) => (
        <TrendChart key={group.variable} group={group} />
      ))}
      <SeriesCharts block={block} />
      {block.groundwater.length > 0 ? <Groundwater values={block.groundwater} /> : null}
      {block.meaning.length > 0 ? (
        <section className="grid min-w-0 gap-1.5" aria-label="For the craft" data-testid="climate-meaning">
          <h4 className="kicker">For the craft</h4>
          <CitedText id={`${block.id}-meaning`} sentences={block.meaning} className="max-w-measure font-reading text-body text-ink-1" />
        </section>
      ) : null}
      <div className="grid min-w-0 gap-2 border-t border-rule pt-3">
        {block.datasets.map((dataset) => (
          <DatasetCredit key={dataset.code} dataset={dataset} />
        ))}
      </div>
    </div>
  );
}

export function ClimateRiskBlockView({ block }: { block: ClimateRiskBlock }) {
  return <ClimateRiskView block={block} />;
}
