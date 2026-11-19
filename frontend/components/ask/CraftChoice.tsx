"use client";

import { ActionGroup } from "@/components/ui/ActionGroup";
import { SearchableSelect } from "@/components/ui/SearchableSelect";
import { ANY_CRAFT, craftPickOf, craftValue, type CraftOffer, type CraftOption, type CraftPick } from "@/lib/askCraft";

export function CraftChoice({
  pick,
  options,
  offer,
  onPick
}: {
  pick: CraftPick;
  options: CraftOption[];
  offer: CraftOffer;
  onPick: (pick: CraftPick) => void;
}) {
  const candidates = offer.candidates;
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2" data-testid="craft-choice">
      <SearchableSelect
        value={craftValue(pick, offer)}
        options={options}
        noneLabel={offer.noneLabel}
        placeholder={ANY_CRAFT}
        onChange={(next) => onPick(craftPickOf(next))}
        ariaLabel="Craft"
        searchable
        advanceOnSelect={false}
        className="w-full sm:w-64"
      />
      {candidates.length > 0 ? (
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="font-ui text-label text-ink-3">Or</span>
          <ActionGroup inline align="start">
            {candidates.map((craft) => (
              <button key={craft.slug} type="button" onClick={() => onPick({ craftSlug: craft.slug, anyCraft: false })} className="kv-chip">
                {craft.name}
              </button>
            ))}
          </ActionGroup>
        </div>
      ) : null}
    </div>
  );
}
