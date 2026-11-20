import Link from "next/link";

import { craftHref, isMonograph } from "@/lib/atlasCollection";
import { ALL_INDIA, type StateCraftList, type StateCrafts } from "@/lib/atlasIndex";
import { stateAnchor, stateListDek } from "@/lib/mapStates";

export const STATE_LIST_HEADING = "Every state and its crafts";

function StateGroup({ group }: { group: StateCraftList }) {
  const id = stateAnchor(group.name);
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="mb-8 break-inside-avoid scroll-mt-6" data-testid="state-crafts-group">
      <h3 id={`${id}-h`} className="flex items-baseline justify-between gap-3 border-b border-ink-1 pb-1.5 font-ui text-h4 text-ink-1">
        <span className="min-w-0">{group.name}</span>
        <b className="font-ui text-ui font-medium text-ink-3 [font-variant-numeric:lining-nums_tabular-nums]">{group.crafts.length}</b>
      </h3>
      <ul className="mt-1">
        {group.crafts.map((craft) => (
          <li key={craft.id} className="flex items-baseline justify-between gap-3 border-b border-rule py-1.5">
            <Link href={craftHref(craft)} className="kv-link min-w-0 font-ui text-ui">
              {craft.displayName}
            </Link>
            {isMonograph(craft) ? <span className="shrink-0 rounded-plate border border-current px-[5px] py-px font-ui text-caption font-medium text-ink-2">Monograph</span> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function StateCraftsList({ lists }: { lists: StateCrafts }) {
  const groups = lists.allIndia.length ? [...lists.states, { name: ALL_INDIA, crafts: lists.allIndia }] : lists.states;
  return (
    <section aria-labelledby="state-crafts-heading" className="border-t border-ink-1 pt-[22px]" data-testid="state-crafts">
      <h2 id="state-crafts-heading" className="font-headline text-h2 text-ink-1">
        {STATE_LIST_HEADING}
      </h2>
      <p className="mt-3 max-w-measure font-reading text-body-sm text-ink-2">{stateListDek(lists.states.length, lists.allIndia.length)}</p>
      <div className="mt-8 columns-1 gap-x-10 sm:columns-2 lg:columns-3 2xl:columns-4">
        {groups.map((group) => (
          <StateGroup key={group.name} group={group} />
        ))}
      </div>
    </section>
  );
}
