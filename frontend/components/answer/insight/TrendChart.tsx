"use client";

import type { CSSProperties } from "react";

import { AnswerFigure } from "@/components/answer/place/AnswerFigure";
import { StripLine } from "@/components/answer/place/StripLine";
import { significanceText, slopeText, TREND_METHOD_TEXT, TREND_WORDS, trendBar, trendContext, trendFinding, type TrendGroup, type TrendVariable } from "@/lib/climateView";
import type { ClimateTrend } from "@/lib/explainerInsight";
import { cn } from "@/lib/utils";

export const TREND_SERIES: Record<TrendVariable, CSSProperties> = {
  annual_precipitation: { color: "var(--series-rain)" },
  annual_mean_temperature: { color: "var(--series-heat)" }
};

export const TREND_KEY = "Solid bars are significant; outlined bars are not.";

function Bar({ trend, domain }: { trend: ClimateTrend; domain: number }) {
  const bar = trendBar(trend.slopePerDecade, domain);
  return (
    <div aria-hidden dir="ltr" className="relative h-3 min-w-0 bg-sunk" style={TREND_SERIES[trend.variable]} data-testid="trend-track">
      <span
        className={cn("absolute inset-y-0", trend.significant ? "bg-current" : "border border-dashed border-current")}
        style={{ left: `${bar.left}%`, width: `${bar.width}%` }}
        data-testid="trend-bar"
        data-left={bar.left}
        data-width={bar.width}
        data-significant={trend.significant ? "true" : "false"}
      />
      <span className="absolute -inset-y-1 inset-x-0 mx-auto w-px bg-ink-1" />
    </div>
  );
}

function TrendRow({ trend, domain }: { trend: ClimateTrend; domain: number }) {
  const label = (
    <span className="grid min-w-0">
      <span className="break-words font-ui text-label font-semibold text-ink-1">{trend.district.name}</span>
      <span className="font-ui text-caption text-ink-3">{trend.district.stateName}</span>
    </span>
  );
  return (
    <li className="min-w-0 border-t border-rule pt-3" data-testid="trend-row">
      <StripLine label={label}>
        <Bar trend={trend} domain={domain} />
        <p className="mt-1.5 flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5 font-ui text-ui font-normal">
          <span className="font-semibold text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]" data-testid="trend-slope">
            {slopeText(trend)}
          </span>
          <span className="text-label text-ink-2" data-testid="trend-significance">
            {significanceText(trend)}
          </span>
        </p>
        <p className="font-ui text-caption text-ink-3 [font-variant-numeric:lining-nums_tabular-nums]" data-testid="trend-context">
          {trendContext(trend)}
        </p>
      </StripLine>
    </li>
  );
}

export function TrendChart({ group }: { group: TrendGroup }) {
  const words = TREND_WORDS[group.variable];
  const texts = { kicker: words.title, title: trendFinding(group), dek: `Method: ${TREND_METHOD_TEXT}. ${TREND_KEY}` };
  return (
    <AnswerFigure texts={texts} data-testid="trend-chart" data-variable={group.variable}>
      <StripLine label={null}>
        <div aria-hidden dir="ltr" className="grid grid-cols-[repeat(3,minmax(0,1fr))] font-ui text-caption text-ink-3" data-testid="trend-axis">
          <span>{words.lower}</span>
          <span className="text-center">0</span>
          <span className="text-end">{words.higher}</span>
        </div>
      </StripLine>
      <ul className="mt-2 grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3">
        {group.trends.map((trend) => (
          <TrendRow key={`${trend.district.districtLgd}-${trend.variable}`} trend={trend} domain={group.domain} />
        ))}
      </ul>
    </AnswerFigure>
  );
}
