"use client";

import { useId, useState } from "react";

import { CollectionPlate } from "@/components/crafts/CollectionPlate";
import { FamilySwatch } from "@/components/crafts/FamilySwatch";
import { PhotoCard } from "@/components/crafts/PhotoCard";
import { TextLink } from "@/components/ui/TextLink";
import { shelfSubLine, type AtlasPlate, type AtlasShelf } from "@/lib/atlasCollection";
import type { NativeName } from "@/lib/editorialText";
import { cn } from "@/lib/utils";

export type ShelfNames = ReadonlyMap<string, NativeName>;
export type ShelfAll = { href: string } | { expand: AtlasPlate[] };

const GRID =
  "grid grid-flow-col auto-cols-[72%] gap-3 overflow-x-auto overscroll-x-contain snap-x snap-mandatory pb-2.5 [scrollbar-width:thin] sm:auto-cols-auto sm:grid-flow-row sm:grid-cols-2 sm:overflow-visible sm:pb-0 md:grid-flow-row-dense md:grid-cols-4 md:gap-3.5 lg:grid-cols-6 lg:gap-4";

export function leadPlacement(big: boolean, end: boolean): string {
  if (big) return end ? "sm:col-span-full md:col-[3/span_2] md:row-[1/span_2] lg:col-[5/span_2]" : "sm:col-span-full md:col-span-2 md:row-span-2";
  return end ? "sm:col-span-full md:col-[3/span_2] md:row-start-1 lg:col-[5/span_2]" : "sm:col-span-full md:col-span-2";
}

function Lead({ shelf, names, priority }: { shelf: AtlasShelf; names?: ShelfNames; priority: boolean }) {
  const lead = shelf.lead;
  if (!lead) return null;
  const place = cn("snap-start", leadPlacement(shelf.big, shelf.leadEnd));
  if (lead.craft.hero) return <PhotoCard plate={lead} hero={lead.craft.hero} big={shelf.big} priority={priority} className={place} />;
  return <CollectionPlate plate={lead} nativeName={names?.get(lead.craft.slug) ?? null} lead className={place} />;
}

type ShelfMore = { href: string | null; expandable: boolean; open: boolean; onToggle: () => void; gridId: string };

function ShelfHead({ shelf, level, more }: { shelf: AtlasShelf; level: 2 | 3; more: ShelfMore }) {
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <div className="mb-4 flex flex-wrap items-baseline gap-x-[18px] gap-y-1.5 border-b border-ink-1 pb-3.5">
      <Heading className="flex items-center gap-3 font-reading text-h3 text-ink-1">
        <FamilySwatch material={shelf.material} className="h-[22px] w-4 self-center" />
        {shelf.name}
        <b className="font-ui text-ui-lg font-medium text-ink-3 [font-variant-numeric:tabular-nums]">{shelf.count}</b>
      </Heading>
      {shelf.subFamilies.length ? <p className="min-w-0 flex-[1_1_320px] font-ui text-label font-normal text-ink-3">{shelfSubLine(shelf.subFamilies)}</p> : null}
      {more.href ? (
        <TextLink href={more.href} standalone className="ms-auto">
          {`All ${shelf.count}`}
        </TextLink>
      ) : more.expandable ? (
        <TextLink onClick={more.onToggle} expanded={more.open} controls={more.gridId} standalone className="ms-auto">
          {more.open ? "Show fewer" : `Show all ${shelf.count}`}
        </TextLink>
      ) : null}
    </div>
  );
}

export function CollectionShelf({ id, shelf, level = 3, all, names, priority = false }: { id?: string; shelf: AtlasShelf; level?: 2 | 3; all?: ShelfAll; names?: ShelfNames; priority?: boolean }) {
  const [open, setOpen] = useState(false);
  const gridId = useId();
  const href = all && "href" in all ? all.href : null;
  const expand = all && "expand" in all ? all.expand : [];
  const extra = open ? expand : [];
  const more = { href, expandable: expand.length > 0, open, onToggle: () => setOpen((value) => !value), gridId };
  return (
    <section id={id} aria-label={shelf.name} className="min-w-0 scroll-mt-6" data-testid="collection-shelf" data-big={shelf.big || undefined}>
      <ShelfHead shelf={shelf} level={level} more={more} />
      <div id={gridId} className={GRID}>
        <Lead shelf={shelf} names={names} priority={priority} />
        {[...shelf.plates, ...extra].map((plate) => (
          <CollectionPlate key={plate.craft.id} plate={plate} nativeName={names?.get(plate.craft.slug) ?? null} className="snap-start" />
        ))}
      </div>
    </section>
  );
}
