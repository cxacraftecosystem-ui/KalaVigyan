import { byCount, bytes, countNoun, formatCalendarDay } from "@/lib/format";
import type { DatasetTable, OpenDataListing, PublishedRelease, ReleaseFile } from "@/lib/openDataContract";

export type GlanceFact = { label: string; value: string; href?: string };
export type ReleaseRow = { version: string; released: string; doi: string; doiUrl: string; recordUrl: string; size: string; files: string; facts: string; changes: string };
export type TableHolding = { table: DatasetTable; rows: string | null; files: ReleaseFile[] };

export const FACT_TABLE = "claims";
const SOURCE_TABLE = "sources";
const CRAFT_TABLE = "crafts";
const NUMBERS = new Intl.NumberFormat("en-IN");
const FIRST_RELEASE = "First release";
const UNCHANGED = "Facts unchanged";

export function licenceLabel(id: string): string {
  return id.replace(/-/g, " ");
}

export function counted(value: number): string {
  return NUMBERS.format(value);
}

export function glanceFacts(listing: OpenDataListing): GlanceFact[] {
  const licence = { label: "Licence", value: licenceLabel(listing.licence.id), href: listing.licence.url };
  const latest = listing.latest;
  if (!latest) {
    return [
      licence,
      { label: "Tables", value: counted(listing.tables.length) },
      { label: "Formats", value: "JSON Lines and CSV, described by a Frictionless descriptor" },
      { label: "Built by", value: "KalaVigyan's open code", href: listing.codeUrl }
    ];
  }
  return [
    licence,
    { label: "This version", value: `${latest.version} · ${formatCalendarDay(latest.releasedOn)}` },
    { label: "DOI of this version", value: latest.doi, href: latest.doiUrl },
    ...(listing.conceptDoi && listing.conceptDoiUrl ? [{ label: "DOI of every version", value: listing.conceptDoi, href: listing.conceptDoiUrl }] : []),
    { label: "Facts", value: counted(latest.counts[FACT_TABLE] ?? 0) },
    { label: "Sources", value: counted(latest.counts[SOURCE_TABLE] ?? 0) },
    { label: "Crafts", value: counted(latest.counts[CRAFT_TABLE] ?? 0) },
    { label: "Size", value: `${bytes(latest.totalBytes)} in ${countNoun(latest.files.length, "file")}` }
  ];
}

export function changeLine(release: PublishedRelease, first: boolean): string {
  if (first) return FIRST_RELEASE;
  const facts = release.changes[FACT_TABLE];
  if (!facts || facts.added + facts.removed + facts.changed === 0) return UNCHANGED;
  return `${counted(facts.added)} facts added, ${counted(facts.removed)} removed, ${counted(facts.changed)} changed`;
}

export function releaseRows(releases: readonly PublishedRelease[]): ReleaseRow[] {
  return releases.map((release, index) => ({
    version: release.version,
    released: formatCalendarDay(release.releasedOn),
    doi: release.doi,
    doiUrl: release.doiUrl,
    recordUrl: release.recordUrl,
    size: bytes(release.totalBytes),
    files: counted(release.files.length),
    facts: counted(release.counts[FACT_TABLE] ?? 0),
    changes: changeLine(release, index === releases.length - 1)
  }));
}

export function tableHoldings(listing: OpenDataListing): TableHolding[] {
  const files = new Map((listing.latest?.files ?? []).map((file) => [file.path, file]));
  return listing.tables.map((table) => {
    const count = listing.latest?.counts[table.name];
    return {
      table,
      rows: count === undefined ? null : `${counted(count)} ${byCount(count, "row", "rows")}`,
      files: table.files.map((name) => files.get(name)).filter((file): file is ReleaseFile => file !== undefined)
    };
  });
}
