"use client";

import { useId, useState } from "react";

import { CollectionPlate } from "@/components/crafts/CollectionPlate";
import { PhotoCard } from "@/components/crafts/PhotoCard";
import { DOCUMENTS_SHOWN } from "@/components/landing/landingCollection";
import { TextLink } from "@/components/ui/TextLink";
import type { AtlasPlate } from "@/lib/atlasCollection";

export const DOCUMENTS_HEADING = "Monographs, read in full";

function DocumentCard({ plate }: { plate: AtlasPlate }) {
  if (plate.craft.hero) return <PhotoCard plate={plate} hero={plate.craft.hero} big={false} className="h-full" />;
  return <CollectionPlate plate={plate} className="h-full" />;
}

export function DocumentWall({ documents }: { documents: readonly AtlasPlate[] }) {
  const [open, setOpen] = useState(false);
  const gridId = useId();
  const shown = open ? documents : documents.slice(0, DOCUMENTS_SHOWN);
  return (
    <div className="mt-14" data-testid="landing-documents">
      <div className="mb-4 flex flex-wrap items-baseline gap-x-[18px] gap-y-1.5 border-b border-ink-1 pb-3.5">
        <h3 className="flex items-baseline gap-3 font-reading text-h3 text-ink-1">
          {DOCUMENTS_HEADING}
          <b className="font-ui text-ui-lg font-medium text-ink-3 [font-variant-numeric:tabular-nums]">{documents.length}</b>
        </h3>
        <p className="min-w-0 flex-[1_1_320px] font-ui text-label font-normal text-ink-3">Each is one continuous page: how it is made, its science, its place, its history and its people, every sentence cited.</p>
        {documents.length > DOCUMENTS_SHOWN ? (
          <TextLink onClick={() => setOpen((value) => !value)} expanded={open} controls={gridId} standalone className="ms-auto">
            {open ? "Show fewer" : `Show all ${documents.length}`}
          </TextLink>
        ) : null}
      </div>
      <ul id={gridId} className="grid grid-cols-2 gap-3 md:gap-3.5 lg:grid-cols-4 lg:gap-4">
        {shown.map((plate) => (
          <li key={plate.craft.id} className="min-w-0">
            <DocumentCard plate={plate} />
          </li>
        ))}
      </ul>
    </div>
  );
}
