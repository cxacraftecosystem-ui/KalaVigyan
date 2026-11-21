import type { RegionDataset } from "@/lib/regionContract";

export const SHA_SHOWN = 12;

const READ_DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

export function readDate(day: string): string | null {
  const parsed = new Date(`${day}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? null : READ_DATE.format(parsed);
}

export function datasetReadLine(dataset: RegionDataset): string | null {
  const day = dataset.readOn ? readDate(dataset.readOn) : null;
  const parts = [
    dataset.crs ? `Coordinates ${dataset.crs}` : null,
    dataset.nativeResolution ? `native resolution ${dataset.nativeResolution}` : null,
    day ? `read ${day}` : null,
    dataset.sha256 ? `SHA-256 ${dataset.sha256.slice(0, SHA_SHOWN)}` : null
  ].filter((part): part is string => part !== null);
  return dataset.version && parts.length ? parts.join(" · ") : null;
}
