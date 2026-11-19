"use client";

import { X } from "lucide-react";

import { FieldBlock } from "@/components/FormControls";
import { SearchableSelect } from "@/components/ui/SearchableSelect";
import type { CraftOption } from "@/lib/askCraft";
import { COMPARE_CRAFTS_MAX } from "@/lib/comparePage";

export function ComparePicker({ slugs, options, onChange }: { slugs: readonly string[]; options: readonly CraftOption[]; onChange: (slugs: string[]) => void }) {
  const names = new Map(options.map((option) => [option.value, option.label]));
  const open = options.filter((option) => !slugs.includes(option.value));
  return (
    <div className="grid min-w-0 gap-3 border-y border-rule py-4" data-testid="compare-picker">
      {slugs.length > 0 ? (
        <ul className="flex min-w-0 flex-wrap gap-2" aria-label="Crafts to compare">
          {slugs.map((slug) => (
            <li key={slug} className="flex min-w-0 max-w-full items-center gap-1 rounded-pill border border-rule-strong bg-raised pe-1 ps-3 font-ui text-label text-ink-1">
              <span className="min-w-0 truncate">{names.get(slug) ?? slug}</span>
              <button
                type="button"
                className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-ink-3 transition-colors duration-state hover:bg-sunk hover:text-ink-1 pointer-coarse:h-11 pointer-coarse:w-11"
                aria-label={`Remove ${names.get(slug) ?? slug}`}
                onClick={() => onChange(slugs.filter((held) => held !== slug))}
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {slugs.length < COMPARE_CRAFTS_MAX ? (
        <div className="sm:max-w-sm">
          <FieldBlock label={slugs.length === 0 ? "Choose a craft" : "Add a craft"}>
            <SearchableSelect value="" options={[...open]} placeholder="Search crafts" onChange={(slug) => slug && onChange([...slugs, slug])} searchable advanceOnSelect={false} />
          </FieldBlock>
        </div>
      ) : null}
    </div>
  );
}
