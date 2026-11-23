import { UnitView } from "@/components/monograph/UnitView";
import type { MonographUnit } from "@/lib/monographDocument";
import type { MonographSources } from "@/lib/monographRender";

export const CITED_LIST_CLASS = "kv-list border-t border-rule";
export const CITED_ITEM_CLASS = "border-b border-rule py-3 font-reading text-body-sm text-ink-1";

type CitedListProps = { units: Readonly<Record<string, MonographUnit>>; sources: MonographSources; refs: readonly string[] };

export function CitedList({ units, sources, refs }: CitedListProps) {
  return (
    <div className="mt-4 mb-6">
      <ul className={CITED_LIST_CLASS}>
        {refs.map((ref) => (
          <UnitView key={ref} unit={units[ref]} sources={sources} as="li" className={CITED_ITEM_CLASS} />
        ))}
      </ul>
    </div>
  );
}
