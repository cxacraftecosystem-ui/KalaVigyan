import type { MonthlyRain, Season } from "@/lib/explainerPlace";
import { numberRuns } from "@/lib/format";
import { formatNumber } from "@/lib/measure";

export const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"] as const;
export const MONTHS = MONTH_NAMES.map((_, index) => index + 1);
export const SEASON_LABEL: Record<Season, string> = { MONSOON: "Monsoon", WINTER: "Winter", SUMMER: "Summer" };

const WHOLE_FROM = 10;

export function monthInitial(month: number): string {
  return MONTH_NAMES[month - 1].slice(0, 1);
}

export function monthsText(months: readonly number[]): string {
  return numberRuns(months)
    .map((run) => run.split("–").map((month) => MONTH_NAMES[Number(month) - 1]).join("–"))
    .join(", ");
}

export function rainText(millimetres: number): string {
  return `${formatNumber(millimetres, millimetres >= WHOLE_FROM ? 0 : 1)} mm`;
}

export function wettestMonth(rain: MonthlyRain): number {
  return rain.millimetres.reduce((wettest, value, index) => (value > rain.millimetres[wettest - 1] ? index + 1 : wettest), 1);
}

export function rainShares(rain: MonthlyRain): number[] {
  const most = Math.max(...rain.millimetres);
  return rain.millimetres.map((value) => (most > 0 ? value / most : 0));
}

export function monthReading(rain: MonthlyRain, month: number): string {
  return `${MONTH_NAMES[month - 1]} · ${rainText(rain.millimetres[month - 1])}`;
}

export function annualRain(rain: MonthlyRain): number {
  return rain.millimetres.reduce((total, value) => total + value, 0);
}

export function rainfallFinding(rain: MonthlyRain): string {
  const wettest = wettestMonth(rain);
  const month = MONTH_NAMES[wettest - 1];
  return `${month} is the wettest month in ${rain.district.name}: ${rainText(rain.millimetres[wettest - 1])} of a ${rainText(annualRain(rain))} year`;
}
