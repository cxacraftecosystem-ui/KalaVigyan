"use client";

import { useEffect, useMemo, useState } from "react";

import { TextInput } from "@/components/FormControls";
import { fetchCraftPage } from "@/lib/craftPageChecks";
import type { PageClaim } from "@/lib/craftPageContract";
import { IMAGE_FACTS_MAX } from "@/lib/imageContributionContract";

const SHOWN_MAX = 40;

export function PictureFactsPicker({
  craftSlug,
  chosen,
  onChange
}: {
  craftSlug: string;
  chosen: string[];
  onChange: (next: string[]) => void;
}) {
  const [facts, setFacts] = useState<PageClaim[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [term, setTerm] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchCraftPage(craftSlug)
      .then((page) => {
        if (!cancelled) setFacts(page.claims);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [craftSlug]);

  const shown = useMemo(() => {
    const words = term.trim().toLowerCase();
    const matching = (facts ?? []).filter((fact) => !words || fact.text.toLowerCase().includes(words) || chosen.includes(fact.id));
    return matching.slice(0, SHOWN_MAX);
  }, [facts, term, chosen]);

  if (failed) return <p className="text-ui font-ui text-error">Couldn&apos;t load this craft&apos;s facts. Reload the page.</p>;
  if (!facts) return <p role="status" className="text-ui font-ui text-ink-3">Loading this craft&apos;s facts</p>;

  function toggle(id: string) {
    if (chosen.includes(id)) onChange(chosen.filter((each) => each !== id));
    else if (chosen.length < IMAGE_FACTS_MAX) onChange([...chosen, id]);
  }

  return (
    <div className="grid gap-2" data-testid="picture-facts">
      <TextInput value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Find a fact" aria-label="Find a fact" />
      <p className="text-label font-ui text-ink-3" role="status">
        {chosen.length} of {IMAGE_FACTS_MAX} chosen
      </p>
      <ul className="grid max-h-80 gap-1 overflow-y-auto border-y border-rule py-2">
        {shown.map((fact) => (
          <li key={fact.id}>
            <label className="flex min-h-target items-start gap-3 py-1 text-body-sm font-reading text-ink-1">
              <input type="checkbox" className="mt-1.5 h-4 w-4 shrink-0" checked={chosen.includes(fact.id)} onChange={() => toggle(fact.id)} />
              <span>{fact.text}</span>
            </label>
          </li>
        ))}
      </ul>
    </div>
  );
}
