"use client";

import Link from "next/link";
import { GitCompareArrows, X } from "lucide-react";

import { ListedSources } from "@/components/answer/CitedReading";
import { ExplainerBlockView } from "@/components/answer/ExplainerBlockView";
import { BasisLine, FacetBlock } from "@/components/map/PlaceFacts";
import { DatasetCredit } from "@/components/DatasetCredit";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { buttonLook } from "@/components/ui/button";
import { IconButton } from "@/components/ui/IconButton";
import { compareHref, COMPARE_CRAFTS_MAX } from "@/lib/comparePage";
import { PLACE_ROLE_LABEL } from "@/lib/craftPlaces";
import type { DistrictCraft, DistrictCrafts } from "@/lib/districtCraftsContract";
import { craftsHeading, districtTitle } from "@/lib/districtView";
import { datasetIndex } from "@/lib/regionView";

function CraftRow({ entry }: { entry: DistrictCraft }) {
  return (
    <li className="grid min-w-0 gap-1 border-t border-rule py-3" data-testid="district-craft">
      <Link href={entry.craft.path} className="kv-link min-w-0 break-words font-reading text-body">
        {entry.craft.name}
      </Link>
      <p className="font-ui text-label text-ink-2">{entry.roles.map((role) => PLACE_ROLE_LABEL[role]).join(" · ")}</p>
      <BasisLine basis={entry.basis} />
    </li>
  );
}

function LandStory({ district, reduce }: { district: DistrictCrafts; reduce: boolean }) {
  const land = district.land;
  if (!land) return null;
  const datasets = datasetIndex(district.datasets);
  return (
    <section aria-labelledby="district-land" className="grid min-w-0 gap-4" data-testid="district-land">
      <h3 id="district-land" className="font-reading text-h3 text-ink-1">
        Why the land suits them
      </h3>
      {land.blocks.map((block) => (
        <ExplainerBlockView key={block.id} block={block} reduce={reduce} />
      ))}
      {land.facets.length > 0 ? (
        <div className="grid min-w-0 gap-x-8 gap-y-5 md:grid-cols-2">
          {land.facets.map((facet) => (
            <FacetBlock key={facet.facet} facet={facet} datasets={datasets} />
          ))}
        </div>
      ) : null}
    </section>
  );
}

function CompareLink({ href }: { href: string }) {
  return (
    <ActionGroup align="start">
      <Link href={href} {...buttonLook({ variant: "quiet" })}>
        <GitCompareArrows className="h-4 w-4 shrink-0" aria-hidden />
        Compare these crafts
      </Link>
    </ActionGroup>
  );
}

export function DistrictView({ district, reduce, onClose }: { district: DistrictCrafts; reduce: boolean; onClose: () => void }) {
  const compare = district.crafts.length >= 2 ? compareHref(district.crafts.slice(0, COMPARE_CRAFTS_MAX).map((entry) => entry.craft.slug)) : null;
  return (
    <article className="grid min-w-0 gap-6" data-testid="district-view" data-lgd={district.district.districtLgd}>
      <header className="flex min-w-0 items-start justify-between gap-3">
        <div className="grid min-w-0 gap-1">
          <p className="kicker">Selected district</p>
          <h2 className="break-words font-headline text-h2 text-ink-1">{districtTitle(district.district)}</h2>
        </div>
        <IconButton label="Close the district" icon={<X className="h-4 w-4" />} edge onClick={onClose} />
      </header>
      <section aria-labelledby="district-crafts" className="grid min-w-0 gap-3">
        <h3 id="district-crafts" className="font-reading text-h3 text-ink-1">
          {craftsHeading(district.crafts.length)}
        </h3>
        {district.crafts.length > 0 ? (
          <ul className="grid min-w-0 gap-x-8 border-b border-rule sm:grid-cols-2">
            {district.crafts.map((entry) => (
              <CraftRow key={entry.craft.slug} entry={entry} />
            ))}
          </ul>
        ) : null}
        {compare ? <CompareLink href={compare} /> : null}
      </section>
      <LandStory district={district} reduce={reduce} />
      <ListedSources sources={district.sources} idPrefix="district-source" />
      <footer className="grid min-w-0 gap-2" data-testid="district-credits">
        {district.datasets.map((dataset) => (
          <DatasetCredit key={dataset.code} dataset={dataset} />
        ))}
        <p className="font-ui text-caption text-ink-3" data-testid="district-boundary">
          {district.boundaryCaption}
        </p>
      </footer>
    </article>
  );
}
