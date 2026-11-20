"use client";

import { failureMessage } from "@/components/hooks/useRemote";
import { NATURAL_EARTH_CREDIT } from "@/components/map/boardGeometry";
import { placeExtra, SALT_EXTRA, WATER_EXTRA } from "@/components/map/ChoroplethLegend";
import { CirclesLegend } from "@/components/map/CirclesLegend";
import { MapCanvas } from "@/components/map/MapCanvas";
import { SURVEY_OF_INDIA_CAPTION } from "@/components/map/MapAttribution";
import { KachchhPlace } from "@/components/map/MapBase";
import { MapRetry } from "@/components/map/MapRetry";
import { RankedList } from "@/components/map/RankedList";
import { KachchhPin, StateCircles } from "@/components/map/StateCircles";
import { useStateRanking, type StateRanking } from "@/components/map/useStateRanking";
import { Skeleton } from "@/components/ui/Skeleton";
import { TextLink } from "@/components/ui/TextLink";
import { allStatesLabel, mapDescription, rankDek, rankFinding } from "@/lib/mapStates";

export const CRAFTS_MAP_HEADING = "Where the crafts are practised";
export const CRAFTS_MAP_SOURCE = `${SURVEY_OF_INDIA_CAPTION} ${NATURAL_EARTH_CREDIT} Counts from the KalaVigyan craft list.`;
export const CIRCLES_LABEL = "Crafts in a state; circle area to scale";
const PIN_LINES = ["Kachchh, home of", "Kutch Ajrakh"] as const;
const PLACE_LABEL = "Kachchh, the place this page is about";

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
      <RankedList rows={rows} label="Crafts practised in each state" emphKey={rows[0]?.key ?? null} className="mt-[22px]" />
      <CirclesLegend largest={largest} label={CIRCLES_LABEL} extras={[placeExtra(PLACE_LABEL), SALT_EXTRA, WATER_EXTRA]} className="mt-[18px]" />
      <p className="mt-3.5">
        <TextLink href="/map" standalone>
          {allStatesLabel(counts.states.length)}
        </TextLink>
      </p>
    </>
  );
}

function MapFigure({ ranking }: { ranking: StateRanking }) {
  const emph = ranking.circles[0]?.name ?? null;
  return (
    <figure className="min-w-0" data-testid="crafts-map-figure">
      <MapCanvas
        title="Where India's crafts are practised"
        description={mapDescription(ranking.circles, true)}
        over={(scene) => (
          <>
            <KachchhPlace />
            <StateCircles circles={ranking.circles} emphKey={emph} scene={scene} />
            <KachchhPin lines={PIN_LINES} scene={scene} />
          </>
        )}
      />
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
