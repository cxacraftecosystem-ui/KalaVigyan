import { DataTable } from "@/components/charts/DataTable";
import { TextLink } from "@/components/ui/TextLink";
import type { PublishedRelease } from "@/lib/openDataContract";
import { releaseRows } from "@/lib/openDataView";

const COLUMNS = [
  { key: "version", label: "Version" },
  { key: "released", label: "Released" },
  { key: "doi", label: "DOI" },
  { key: "facts", label: "Facts", numeric: true },
  { key: "size", label: "Size", numeric: true },
  { key: "files", label: "Files", numeric: true },
  { key: "changes", label: "Changes" }
] as const;

export function ReleaseHistory({ releases }: { releases: readonly PublishedRelease[] }) {
  const rows = releaseRows(releases).map((row) => ({
    key: row.version,
    cells: {
      version: <span className="lining-nums tabular-nums">{row.version}</span>,
      released: <span className="lining-nums tabular-nums">{row.released}</span>,
      doi: (
        <TextLink href={row.doiUrl} external>
          {row.doi}
        </TextLink>
      ),
      facts: row.facts,
      size: row.size,
      files: row.files,
      changes: <span className="text-ink-2">{row.changes}</span>
    }
  }));
  return (
    <div className="min-w-0 overflow-x-auto" data-testid="open-data-releases">
      <DataTable caption="Every release of KalaVigyan open knowledge" columns={COLUMNS} rows={rows} />
    </div>
  );
}
