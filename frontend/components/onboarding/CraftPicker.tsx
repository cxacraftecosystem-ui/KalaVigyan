"use client";

import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";

import { FormAlert } from "@/components/auth/FormAlert";
import { SearchableSelect } from "@/components/ui/SearchableSelect";
import { isReaderCraft, loadCraftCatalogue, searchCatalogue } from "@/lib/craftCatalogue";
import type { CatalogueCraft, CraftCatalogue } from "@/lib/craftCatalogueContract";
import { ARTISAN_CRAFTS_MAX } from "@/lib/profileContract";

export type PickedCraft = { slug: string; displayName: string };

const OPTIONS_SHOWN = 50;

function craftHint(craft: CatalogueCraft): string {
  return [craft.localName, craft.familyLabel, craft.kindLabel].filter(Boolean).join(" · ");
}

export function CraftPicker({ picked, onChange }: { picked: PickedCraft[]; onChange: (next: PickedCraft[]) => void }) {
  const [catalogue, setCatalogue] = useState<CraftCatalogue | null>(null);
  const [failed, setFailed] = useState(false);
  const [term, setTerm] = useState("");

  useEffect(() => {
    let cancelled = false;
    loadCraftCatalogue()
      .then((loaded) => {
        if (!cancelled) setCatalogue(loaded);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const chosen = useMemo(() => new Set(picked.map((craft) => craft.slug)), [picked]);
  const found = useMemo(() => {
    if (!catalogue) return [];
    return searchCatalogue(catalogue, term).crafts.filter((craft) => isReaderCraft(craft) || craft.isCatchAll);
  }, [catalogue, term]);
  const options = found
    .filter((craft) => !chosen.has(craft.slug))
    .slice(0, OPTIONS_SHOWN)
    .map((craft) => ({ value: craft.slug, label: craft.displayName, hint: craftHint(craft) }));
  const full = picked.length >= ARTISAN_CRAFTS_MAX;

  function add(slug: string) {
    const craft = found.find((each) => each.slug === slug);
    if (!craft || full) return;
    onChange([...picked, { slug: craft.slug, displayName: craft.displayName }]);
    setTerm("");
  }

  if (failed) return <FormAlert>Couldn&apos;t load the crafts. Reload the page.</FormAlert>;

  return (
    <div className="grid gap-2" data-testid="craft-picker">
      <SearchableSelect
        value=""
        onChange={add}
        options={options}
        ariaLabel="Which crafts do you practise?"
        placeholder={full ? `Up to ${ARTISAN_CRAFTS_MAX} crafts` : "Search crafts"}
        disabled={!catalogue || full}
        serverQuery={{ value: term, onChange: setTerm, pending: !catalogue, truncated: found.length - chosen.size > OPTIONS_SHOWN }}
      />
      {picked.length ? (
        <ul className="flex flex-wrap gap-2" aria-label="Your crafts">
          {picked.map((craft) => (
            <li key={craft.slug} className="inline-flex min-w-0 max-w-full items-center gap-1 rounded-pill border border-rule-strong bg-raised pe-1 ps-3 font-ui text-label text-ink-1">
              <span className="min-w-0 truncate">{craft.displayName}</span>
              <button
                type="button"
                aria-label={`Remove ${craft.displayName}`}
                onClick={() => onChange(picked.filter((each) => each.slug !== craft.slug))}
                className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-ink-3 transition-colors duration-state hover:bg-sunk hover:text-ink-1 pointer-coarse:h-11 pointer-coarse:w-11"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
