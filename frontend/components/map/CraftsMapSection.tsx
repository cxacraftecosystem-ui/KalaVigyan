"use client";

import { failureMessage } from "@/components/hooks/useRemote";
import { NATURAL_EARTH_CREDIT } from "@/components/map/basemap";
import { FOREIGN_EXTRA, SALT_EXTRA, WATER_EXTRA } from "@/components/map/ChoroplethLegend";
import { CirclesLegend } from "@/components/map/CirclesLegend";
import { SURVEY_OF_INDIA_CAPTION } from "@/components/map/MapAttribution";
import { MapRetry } from "@/components/map/MapRetry";
import { RankedList } from "@/components/map/RankedList";
import { StatesMapCanvas } from "@/components/map/StatesMapCanvas";
import { useStateRanking, type StateRanking } from "@/components/map/useStateRanking";
import { Skeleton } from "@/components/ui/Skeleton";
import { TextLink } from "@/components/ui/TextLink";
import { LAYER_PARAM } from "@/lib/mapLayers";
import { PHYSICAL_LAYERS } from "@/lib/mapPhysical";
import { allCraftsLabel, allStatesLabel, rankDek, rankFinding } from "@/lib/mapStates";

export const CRAFTS_MAP_HEADING = "Where the crafts are practised";
export const CRAFTS_MAP_SOURCE = `${SURVEY_OF_INDIA_CAPTION} ${NATURAL_EARTH_CREDIT} Counts from the KalaVigyan craft list.`;
export const CIRCLES_LABEL = "Crafts in a state; circle area to scale";
export const MAP_EXTRAS = [SALT_EXTRA, FOREIGN_EXTRA, WATER_EXTRA];

export const MAP_LAYERS_LABEL = "On the full map";
export const SHOWN_DISTRICT_LAYERS = [
  { id: "annual-precipitation", title: "Annual rainfall" },
  { id: "soil-ph-0-5cm", title: "Soil pH" },
  { id: "tree-cover-share", title: "Tree cover" }
] as const;

export function layerHref(id: string): string {
  return `/map?${LAYER_PARAM}=${encodeURIComponent(id)}`;
}

function MapLayerLinks() {
  const layers = [...PHYSICAL_LAYERS.map((layer) => ({ id: layer.id, title: layer.title })), ...SHOWN_DISTRICT_LAYERS];
  return (
    <nav aria-label={MAP_LAYERS_LABEL} className="grid gap-2 border-t border-rule pt-3" data-testid="map-layer-links">
      <p className="font-ui text-label text-ink-3">{MAP_LAYERS_LABEL}</p>
      <ul className="flex flex-wrap gap-x-5 gap-y-2">
        {layers.map((layer) => (
          <li key={layer.id}>
            <TextLink href={layerHref(layer.id)} standalone>
              {layer.title}
            </TextLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function MapSideLinks({ crafts, withMap }: { crafts: number | null; withMap: boolean }) {
  return (
    <div className="grid gap-4">
      {crafts ? (
        <p>
          <TextLink href="/crafts" standalone>
            {allCraftsLabel(crafts)}
          </TextLink>
        </p>
      ) : null}
      {withMap ? <MapLayerLinks /> : null}
    </div>
  );
}

function MapSide({ ranking }: { ranking: StateRanking }) {
  const { counts, rows, circles } = ranking;
  if (!counts) {
    return ranking.catalogueError ? (
      <MapRetry message="The craft list could not be loaded. Try again in a moment." onRetry={ranking.reloadCatalogue} className="mt-6" />
    ) : (
      <Skeleton shape="chart" label="Counting the crafts in each state" className="mt-6" />
    );
  }
  const finding = rankFinding(counts.states);
  const largest = circles[0]?.count ?? counts.states[0]?.count ?? 0;
  return (
    <>
      {finding ? <p className="mt-[18px] font-reading text-h3 text-ink-1 [font-variant-numeric:lining-nums] [text-wrap:balance]">{finding}</p> : null}
      <p className="mt-1.5 max-w-[76ch] font-ui text-ui font-normal text-ink-2">{rankDek(counts.allIndia)}</p>
      <RankedList rows={rows} label="Crafts practised in each state" emphKey={rows[0]?.key ?? null} all={{ label: allStatesLabel(rows.length) }} className="mt-[22px]" />
      <CirclesLegend largest={largest} label={CIRCLES_LABEL} extras={MAP_EXTRAS} className="mt-[18px]" />
      <div className="mt-3.5">
        <MapSideLinks crafts={ranking.catalogue?.summary.crafts ?? null} withMap />
      </div>
    </>
  );
}

function MapFigure({ ranking }: { ranking: StateRanking }) {
  return (
    <figure className="min-w-0" data-testid="crafts-map-figure">
      <StatesMapCanvas ranking={ranking} title="Where India's crafts are practised" />
      {ranking.points.failure ? <MapRetry message={failureMessage(ranking.points.failure, "The craft places could not be loaded.")} onRetry={ranking.points.retry} className="mt-3" /> : null}
      <figcaption className="mt-3 font-ui text-caption text-ink-3">{CRAFTS_MAP_SOURCE}</figcaption>
    </figure>
  );
}

export function CraftsMapSection() {
  const ranking = useStateRanking();
  return (
    <section className="border-t border-rule pt-20 pb-[88px]" aria-labelledby="crafts-map-heading" data-testid="crafts-map-section">
      <div className="kv-shell-wrap">
        <div className="grid grid-cols-1 gap-9 lg:grid-cols-[minmax(0,4.4fr)_minmax(0,6.6fr)] lg:items-start lg:gap-16">
          <div className="min-w-0">
            <p className="kicker flex items-center gap-3 after:h-px after:w-10 after:flex-none after:bg-ink-3 after:content-['']">The atlas</p>
            <h2 id="crafts-map-heading" className="mt-4 font-headline text-h2 text-ink-1">
              {CRAFTS_MAP_HEADING}
            </h2>
            <MapSide ranking={ranking} />
          </div>
          <MapFigure ranking={ranking} />
        </div>
      </div>
    </section>
  );
}
