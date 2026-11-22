import { bytes, formatCalendarDay } from "@/lib/format";
import type { CraftRelease, OpenDataListing } from "@/lib/openDataContract";
import { counted, FACT_TABLE } from "@/lib/openDataView";

export type CraftReleaseRow = {
  key: string;
  craft: string;
  craftHref: string;
  version: string;
  released: string;
  doi: string;
  doiUrl: string;
  conceptDoi: string;
  conceptDoiUrl: string;
  facts: string;
  size: string;
};

const CRAFT_PAGE = /\/crafts\/([^/?#]+)(?:\/v[1-9]\d*)?\/?(?:[?#].*)?$/;

export function craftPageHref(slug: string): string {
  return `/crafts/${encodeURIComponent(slug)}`;
}

export function craftReleaseRows(releases: readonly CraftRelease[]): CraftReleaseRow[] {
  return releases.map((release) => ({
    key: `${release.craft}-${release.version}`,
    craft: release.craftName,
    craftHref: craftPageHref(release.craft),
    version: release.version,
    released: formatCalendarDay(release.releasedOn),
    doi: release.doi,
    doiUrl: release.doiUrl,
    conceptDoi: release.conceptDoi,
    conceptDoiUrl: release.conceptDoiUrl,
    facts: counted(release.counts[FACT_TABLE] ?? 0),
    size: bytes(release.totalBytes)
  }));
}

export function craftOfPage(url: string): string | null {
  const found = CRAFT_PAGE.exec(url);
  if (!found) return null;
  try {
    return decodeURIComponent(found[1]).toLowerCase();
  } catch {
    return null;
  }
}

function newestFirst(a: CraftRelease, b: CraftRelease): number {
  return b.publishedAt.localeCompare(a.publishedAt) || b.version.localeCompare(a.version);
}

export function craftReleaseFor(listing: OpenDataListing | null, pageUrl: string): CraftRelease | null {
  const craft = craftOfPage(pageUrl);
  if (!listing || !craft) return null;
  const found = listing.craftReleases.filter((release) => release.craft.toLowerCase() === craft);
  return [...found].sort(newestFirst)[0] ?? null;
}
