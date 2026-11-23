import Link from "next/link";

import { RECORD_CELL, RECORD_HEAD_CELL, RECORD_HEAD_ROW, RECORD_NUMBER_CELL, RECORD_ROW, RECORD_TABLE } from "@/components/records/recordTable";
import { HIDDEN_REASON_LABELS, HIDDEN_REASONS, type HiddenRow } from "@/lib/hiddenFacts";
import { formatCount } from "@/lib/usage";
import { cn } from "@/lib/utils";

const CAPTION = "Hidden facts by craft and reason, unexplained first";

function CountCell({ value, strong = false }: { value: number; strong?: boolean }) {
  return <td className={cn(RECORD_NUMBER_CELL, value === 0 ? "text-ink-3" : strong ? "font-semibold text-ink-1" : "text-ink-2")}>{formatCount(value)}</td>;
}

export function HiddenFactsTable({ rows }: { rows: readonly HiddenRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className={`${RECORD_TABLE} min-w-2xl`} data-testid="hidden-facts-table">
        <caption className="sr-only">{CAPTION}</caption>
        <thead>
          <tr className={RECORD_HEAD_ROW}>
            <th scope="col" className={RECORD_HEAD_CELL}>
              Craft
            </th>
            <th scope="col" className={`${RECORD_HEAD_CELL} text-end`}>
              Approved
            </th>
            {HIDDEN_REASONS.map((reason) => (
              <th key={reason} scope="col" className={`${RECORD_HEAD_CELL} text-end`}>
                {HIDDEN_REASON_LABELS[reason]}
              </th>
            ))}
            <th scope="col" className={`${RECORD_HEAD_CELL} text-end`}>
              Unexplained
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.craft} className={RECORD_ROW} data-testid="hidden-facts-craft" data-unexplained={row.unexplained > 0 ? "true" : "false"}>
              <th scope="row" className={`${RECORD_CELL} text-start font-normal`}>
                <Link href={`/crafts/${encodeURIComponent(row.craft)}`} className="kv-link break-all font-code">
                  {row.craft}
                </Link>
              </th>
              <CountCell value={row.approved} />
              {HIDDEN_REASONS.map((reason) => (
                <CountCell key={reason} value={row.reasons[reason]} />
              ))}
              <CountCell value={row.unexplained} strong />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
