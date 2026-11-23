import type { AmountKind, GiStatus, MeasureRegion, MeasureRow, PriceRange, UnitConversion } from "@/lib/explainerInsight";
import { formatCalendarDay } from "@/lib/format";
import { formatRange, measureParts } from "@/lib/measure";
import type { RegionDataset } from "@/lib/regionContract";

export type GiFact = { label: string; value: string };

export const GI_STATUS_LABEL: Record<GiStatus["status"], string> = {
  REGISTERED: "GI registered",
  APPLIED: "GI applied for",
  WITHDRAWN: "GI application withdrawn"
};

export const AMOUNT_KIND_LABEL: Record<AmountKind, string> = {
  TEMPERATURE: "Temperature",
  TIME: "Time",
  MASS: "Mass",
  LENGTH: "Length",
  AREA: "Area",
  VOLUME: "Volume",
  CONCENTRATION: "Concentration",
  SHARE: "Share",
  ACIDITY: "Acidity (pH)"
};

const FACTOR_FORMAT = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 10 });
const MONTH_FORMAT = new Intl.DateTimeFormat("en-IN", { month: "short", year: "numeric", timeZone: "UTC" });
const PARTIAL_DATE = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/;

export function unitName(unit: string): string {
  return unit.replace(/-/g, " ");
}

export function metricText(row: MeasureRow): string {
  const text = formatRange(row.metric.low, row.metric.high ?? row.metric.low, row.metric.unit);
  if (text === null) throw new RangeError(`measure ${row.stated} has no metric value`);
  return text;
}

export function factorText(conversion: UnitConversion): string {
  const parts = measureParts(conversion.metricUnit);
  return `1 ${unitName(conversion.unit)} = ${parts.prefix}${FACTOR_FORMAT.format(conversion.factor)}${parts.suffix}`;
}

export function regionText(region: MeasureRegion): string {
  return region.districtName ? `${region.districtName}, ${region.stateName}` : region.stateName;
}

export function basisText(conversion: UnitConversion): string {
  if (conversion.basis === "DEFINED") return "Exact definition";
  if (!conversion.region) throw new RangeError(`a regional ${conversion.unit} names its region`);
  return `As stated for ${regionText(conversion.region)}`;
}

export function measureDatasets(rows: readonly MeasureRow[]): RegionDataset[] {
  const byCode = new Map<string, RegionDataset>();
  for (const row of rows) if (row.conversion.dataset) byCode.set(row.conversion.dataset.code, row.conversion.dataset);
  return [...byCode.values()];
}

export function partialDateText(value: string): string {
  const parts = PARTIAL_DATE.exec(value);
  if (!parts) throw new RangeError(`not a partial date: ${value}`);
  if (parts[3]) return formatCalendarDay(value);
  if (parts[2]) return MONTH_FORMAT.format(new Date(Date.UTC(Number(parts[1]), Number(parts[2]) - 1, 1)));
  return parts[1];
}

export function giFacts(gi: GiStatus): GiFact[] {
  const facts: (GiFact | null)[] = [
    gi.applicationNumber ? { label: "Application", value: gi.applicationNumber } : null,
    gi.certificateNumber ? { label: "Certificate", value: gi.certificateNumber } : null,
    gi.filedOn ? { label: "Filed", value: partialDateText(gi.filedOn) } : null,
    gi.registeredOn ? { label: "Registered", value: partialDateText(gi.registeredOn) } : null,
    gi.journalIssue ? { label: "GI Journal", value: gi.journalIssue } : null,
    gi.authorisedUserCount !== null ? { label: "Authorised users", value: String(gi.authorisedUserCount) } : null
  ];
  return facts.filter((fact): fact is GiFact => fact !== null);
}

export function priceMeta(price: PriceRange): string {
  return [price.per ? `Per ${price.per}` : null, price.place, partialDateText(price.pricedOn)].filter(Boolean).join(" · ");
}
