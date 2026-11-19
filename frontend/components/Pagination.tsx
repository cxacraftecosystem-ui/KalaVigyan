import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { byCount } from "@/lib/format";

export type CountNoun = { one: string; many: string };

const ENTRIES: CountNoun = { one: "entry", many: "entries" };

export function Pagination({
  page,
  pages,
  total,
  onPage,
  noun = ENTRIES,
  label = "Pages"
}: {
  page: number;
  pages: number;
  total: number;
  onPage: (page: number) => void;
  noun?: CountNoun;
  label?: string;
}) {
  if (total <= 0) return null;
  const countLabel = `${total.toLocaleString("en-IN")} ${byCount(total, noun.one, noun.many)}`;
  return (
    <nav aria-label={label} className="flex flex-col gap-3 border-t border-rule pt-3 sm:flex-row sm:items-center sm:justify-between">
      <span className="font-ui text-label text-ink-3 tabular-nums lining-nums">{pages > 1 ? `Page ${page} of ${pages} · ${countLabel}` : countLabel}</span>
      {pages > 1 ? (
        <ActionGroup align="end">
          <Button variant="quiet" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
            Previous
          </Button>
          <Button variant="quiet" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
            Next
          </Button>
        </ActionGroup>
      ) : null}
    </nav>
  );
}
