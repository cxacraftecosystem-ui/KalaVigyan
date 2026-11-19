import { TREND_VARIABLES, type ClimateTrend, type GroundwaterValue } from "@/lib/explainerInsight";
import { formatMeasure, pText } from "@/lib/measure";
import { variableLabel } from "@/lib/regionView";

export type TrendVariable = (typeof TREND_VARIABLES)[number];
export type TrendGroup = { variable: TrendVariable; trends: ClimateTrend[]; domain: number };
export type TrendBar = { left: number; width: number; rising: boolean };
export type TrendWords = { title: string; noun: string; lower: string; higher: string };

export const TREND_SIGNIFICANCE = 0.05;
export const TREND_METHOD_TEXT = `Theil–Sen slope per decade; Mann–Kendall test, significant below p = ${TREND_SIGNIFICANCE}`;

export const TREND_WORDS: Record<TrendVariable, TrendWords> = {
  annual_precipitation: { title: "Rainfall trend", noun: "Rainfall", lower: "Drier", higher: "Wetter" },
  annual_mean_temperature: { title: "Temperature trend", noun: "Mean temperature", lower: "Cooler", higher: "Warmer" }
};

const NICE_STEPS = [1, 2, 2.5, 5, 10];

export function niceCeiling(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  const step = NICE_STEPS.find((candidate) => candidate * power >= value) ?? 10;
  return step * power;
}

export function trendGroups(trends: readonly ClimateTrend[]): TrendGroup[] {
  return TREND_VARIABLES.flatMap((variable) => {
    const shown = trends.filter((trend) => trend.variable === variable);
    if (shown.length === 0) return [];
    const largest = Math.max(...shown.map((trend) => Math.abs(trend.slopePerDecade)));
    return [{ variable, trends: shown, domain: niceCeiling(largest) }];
  });
}

export function trendBar(slope: number, domain: number): TrendBar {
  const width = Math.round(Math.min(1, Math.abs(slope) / domain) * 5000) / 100;
  const rising = slope >= 0;
  return { left: rising ? 50 : Math.round((50 - width) * 100) / 100, width, rising };
}

export function slopeText(trend: ClimateTrend): string {
  const shown = formatMeasure(trend.slopePerDecade, trend.slopeUnit);
  return trend.slopePerDecade > 0 ? `+${shown}` : shown;
}

export function significanceText(trend: ClimateTrend): string {
  return `${trend.significant ? "Significant" : "Not significant"} · ${pText(trend.pValue)}`;
}

export function trendContext(trend: ClimateTrend): string {
  return [`Mean ${formatMeasure(trend.mean, trend.meanUnit)}`, trend.period.replace("-", "–"), trend.resolution].join(" · ");
}

export function groundwaterReading(value: GroundwaterValue): string {
  if (value.value !== null && value.unit) {
    const measured = formatMeasure(value.value, value.unit);
    return value.valueText ? `${value.valueText} · ${measured}` : measured;
  }
  if (value.valueText) return value.valueText;
  throw new RangeError(`groundwater ${value.datasetCode}.${value.variable} has a value or a value text`);
}

export function groundwaterLabel(value: GroundwaterValue): string {
  return variableLabel(value.variable);
}

function changeWord(slope: number): string {
  return slope >= 0 ? "risen" : "fallen";
}

export function trendFinding(group: TrendGroup): string {
  const noun = TREND_WORDS[group.variable].noun;
  if (group.trends.length === 1) {
    const [trend] = group.trends;
    if (!trend.significant) return `${noun} in ${trend.district.name} shows no significant trend`;
    return `${noun} in ${trend.district.name} has ${changeWord(trend.slopePerDecade)} by ${formatMeasure(Math.abs(trend.slopePerDecade), trend.slopeUnit)}`;
  }
  const rising = group.trends.filter((trend) => trend.significant && trend.slopePerDecade > 0).length;
  const falling = group.trends.filter((trend) => trend.significant && trend.slopePerDecade < 0).length;
  const total = group.trends.length;
  if (rising === 0 && falling === 0) return `${noun} shows no significant trend in any of the ${total} districts`;
  return rising >= falling ? `${noun} has risen significantly in ${rising} of ${total} districts` : `${noun} has fallen significantly in ${falling} of ${total} districts`;
}
