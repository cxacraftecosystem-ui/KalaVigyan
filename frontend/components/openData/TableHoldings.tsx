import { DataTable } from "@/components/charts/DataTable";
import { TextLink } from "@/components/ui/TextLink";
import { bytes } from "@/lib/format";
import type { DatasetTable } from "@/lib/openDataContract";
import type { TableHolding } from "@/lib/openDataView";

const FIELD_COLUMNS = [
  { key: "field", label: "Field" },
  { key: "type", label: "Type" },
  { key: "meaning", label: "Meaning" }
] as const;

function fieldRows(table: DatasetTable) {
  return table.fields.map((field) => ({
    key: field.name,
    cells: {
      field: <code className="font-code text-label text-ink-1">{field.name}</code>,
      type: <span className="text-ink-2">{field.required ? field.type : `${field.type}, may be empty`}</span>,
      meaning: <span className="font-reading text-body-sm text-ink-1">{field.description}</span>
    }
  }));
}

function Files({ holding }: { holding: TableHolding }) {
  if (holding.files.length === 0) {
    return <p className="font-code text-label text-ink-3">{holding.table.files.join(" · ")}</p>;
  }
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 font-ui text-label text-ink-3">
      {holding.files.map((file) => (
        <li key={file.path}>
          <TextLink href={file.downloadUrl} external>
            {file.path}
          </TextLink>{" "}
          <span className="lining-nums tabular-nums">{bytes(file.bytes)}</span>
        </li>
      ))}
    </ul>
  );
}

function Holding({ holding }: { holding: TableHolding }) {
  const { table } = holding;
  return (
    <article className="grid min-w-0 content-start gap-2 border-t border-rule pt-3" data-testid="open-data-table">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="font-reading text-h3 text-ink-1">{table.title}</h3>
        {holding.rows ? <p className="font-ui text-label text-ink-3 lining-nums tabular-nums">{holding.rows}</p> : null}
      </div>
      <p className="max-w-measure font-reading text-body-sm text-ink-2">{table.description}</p>
      <Files holding={holding} />
      <details className="min-w-0">
        <summary className="kv-link w-fit cursor-pointer font-ui text-ui">{`Show the ${table.fields.length} fields`}</summary>
        <p className="mt-3 font-ui text-label text-ink-3">
          Keyed by <code className="font-code">{table.key.join(", ")}</code>
        </p>
        <div className="mt-2 min-w-0 overflow-x-auto">
          <DataTable caption={`The fields of ${table.title.toLowerCase()}`} columns={FIELD_COLUMNS} rows={fieldRows(table)} />
        </div>
      </details>
    </article>
  );
}

export function TableHoldings({ holdings }: { holdings: readonly TableHolding[] }) {
  return (
    <div className="grid min-w-0 gap-x-10 gap-y-6 md:grid-cols-2">
      {holdings.map((holding) => (
        <Holding key={holding.table.name} holding={holding} />
      ))}
    </div>
  );
}
