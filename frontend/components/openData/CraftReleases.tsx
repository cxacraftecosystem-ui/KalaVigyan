import { DataTable } from "@/components/charts/DataTable";
import { OpenDataSection } from "@/components/openData/OpenDataSection";
import { TextLink } from "@/components/ui/TextLink";
import type { CraftRelease } from "@/lib/openDataContract";
import { craftReleaseRows } from "@/lib/openDataCrafts";

export const CRAFT_RELEASES_TITLE = "Releases of one craft";
export const CRAFT_RELEASES_LEAD = "Each holds one craft's slice of this dataset under the same licence, with the same things left out, and is cited by a DOI of its own.";

const COLUMNS = [
  { key: "craft", label: "Craft" },
  { key: "version", label: "Version" },
  { key: "released", label: "Released" },
  { key: "doi", label: "DOI" },
  { key: "every", label: "Every version" },
  { key: "facts", label: "Facts", numeric: true },
  { key: "size", label: "Size", numeric: true }
] as const;

export function CraftReleases({ releases }: { releases: readonly CraftRelease[] }) {
  const rows = craftReleaseRows(releases).map((row) => ({
    key: row.key,
    cells: {
      craft: <TextLink href={row.craftHref}>{row.craft}</TextLink>,
      version: <span className="lining-nums tabular-nums">{row.version}</span>,
      released: <span className="lining-nums tabular-nums">{row.released}</span>,
      doi: (
        <TextLink href={row.doiUrl} external>
          {row.doi}
        </TextLink>
      ),
      every: (
        <TextLink href={row.conceptDoiUrl} external>
          {row.conceptDoi}
        </TextLink>
      ),
      facts: row.facts,
      size: row.size
    }
  }));
  return (
    <OpenDataSection id="open-data-crafts" title={CRAFT_RELEASES_TITLE} lead={CRAFT_RELEASES_LEAD}>
      <div className="min-w-0 overflow-x-auto" data-testid="open-data-craft-releases">
        <DataTable caption="Every release of one craft of KalaVigyan open knowledge" columns={COLUMNS} rows={rows} />
      </div>
    </OpenDataSection>
  );
}
