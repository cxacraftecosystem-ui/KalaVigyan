"use client";

import { Fragment } from "react";
import { ArrowRight } from "lucide-react";

import { ChemEquation } from "@/components/answer/ChemEquation";
import { reactionSpoken, speciesSides, type SpeciesReaction, type SpeciesTerm } from "@/lib/processView";

export function SpeciesRow({ reaction }: { reaction: SpeciesReaction }) {
  const { reactants, products } = speciesSides(reaction);
  return (
    <div className="mt-3">
      <p className="sr-only">{reactionSpoken(reaction)}</p>
      <p aria-hidden className="flex flex-wrap items-center gap-x-2 gap-y-1.5 font-ui text-ui text-ink-2">
        <SpeciesGroup species={reactants} />
        <ArrowRight className="h-4 w-4 shrink-0 text-ink-3 rtl:-scale-x-100" />
        <SpeciesGroup species={products} />
      </p>
    </div>
  );
}

function SpeciesGroup({ species }: { species: readonly SpeciesTerm[] }) {
  return species.map((entry, index) => (
    <Fragment key={`${entry.formula ?? ""}:${entry.name ?? ""}:${index}`}>
      {index > 0 ? <span className="text-ink-3">+</span> : null}
      <span className="inline-flex items-center gap-1.5 rounded-pill border border-rule bg-sunk px-2.5 py-0.5">
        {entry.formula ? <ChemEquation equation={entry.formula} display={false} label={entry.formula} /> : null}
        {entry.name ? <span className="font-ui text-caption text-ink-2">{entry.name}</span> : null}
      </span>
    </Fragment>
  ));
}
