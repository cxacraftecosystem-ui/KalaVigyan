"use client";

import { DataTable, type DataRow } from "@/components/charts/DataTable";
import { CirclesLegend } from "@/components/map/CirclesLegend";
import { CIRCLES_LABEL, MAP_EXTRAS, MapSideLinks } from "@/components/map/CraftsMapSection";
import { MapRetry } from "@/components/map/MapRetry";
import { MapSourceLine } from "@/components/map/MapSourceLine";
import { RankedList } from "@/components/map/RankedList";
import { StatesMapCanvas } from "@/components/map/StatesMapCanvas";
import type { StateRanking } from "@/components/map/useStateRanking";
import { Figure } from "@/components/ui/Figure";
import { Skeleton } from "@/components/ui/Skeleton";
import { ALL_INDIA, type StateCounts } from "@/lib/atlasIndex";
import { allStatesLabel, rankDek, rankFinding, stateAnchor } from "@/lib/mapStates";
import type { BoundaryNote } from "@/lib/regionContract";

export const STATES_TITLE = "Crafts practised in each state";
const COLUMNS = [
  { key: "state", label: "State or union territory" },
  { key: "crafts", label: "Crafts", numeric: true }
];

export function stateTableRows(counts: StateCounts): DataRow[] {
  const rows: DataRow[] = counts.states.map((state) => ({ key: state.name, cells: { state: state.name, crafts: state.count } }));
  return counts.allIndia > 0 ? [...rows, { key: ALL_INDIA, cells: { state: ALL_INDIA, crafts: counts.allIndia } }] : rows;
}

export const SIDE_BY_SIDE =
  "lg:grid lg:grid-cols-[minmax(0,6.6fr)_minmax(0,4.4fr)] lg:grid-rows-[auto_1fr] lg:gap-x-12 lg:[&>figcaption]:col-start-2 lg:[&>figcaption]:row-start-1 lg:[&>div]:contents lg:[&>p]:col-span-2 lg:[&>details]:col-span-2";
export const MAP_PLACE = "min-w-0 lg:col-start-1 lg:row-span-2 lg:row-start-1";
export const SIDE_PLACE = "mt-8 grid content-start gap-[18px] lg:col-start-2 lg:row-start-2 lg:mt-6";

function StatesSide({ ranking }: { ranking: StateRanking }) {
  const { counts, rows, circles } = ranking;
  if (!counts) {
    return ranking.catalogueError ? (
      <MapRetry message="The craft list could not be loaded. Try again in a moment." onRetry={ranking.reloadCatalogue} />
    ) : (
      <Skeleton shape="chart" label="Counting the crafts in each state" />
    );
  }
  const listed = rows.map((row) => ({ ...row, href: `#${stateAnchor(row.name)}` }));
  return (
    <>
      <p className="font-ui text-ui font-normal text-ink-2">{rankDek(counts.allIndia)}</p>
      <RankedList rows={listed} label={STATES_TITLE} emphKey={rows[0]?.key ?? null} all={{ label: allStatesLabel(rows.length) }} />
      <CirclesLegend largest={circles[0]?.count ?? 0} label={CIRCLES_LABEL} extras={MAP_EXTRAS} />
      <MapSideLinks crafts={ranking.catalogue?.summary.crafts ?? null} withMap={false} />
    </>
  );
}

export function MapStatesFigure({ ranking, boundary }: { ranking: StateRanking; boundary: BoundaryNote | null }) {
  const { counts } = ranking;
  const tableRows = counts ? stateTableRows(counts) : null;
  const table = tableRows ? <DataTable caption={STATES_TITLE} columns={COLUMNS} rows={tableRows} /> : undefined;
  return (
    <Figure
      number={1}
      kind="map"
      id="map-figure"
      title={STATES_TITLE}
      dek={counts ? rankFinding(counts.states) : undefined}
      source={<MapSourceLine boundary={boundary} districts={false} counts />}
      table={table}
      valueCount={tableRows?.length}
      className={SIDE_BY_SIDE}
    >
      <div className={MAP_PLACE} data-testid="map-states-plot">
        <StatesMapCanvas ranking={ranking} title={STATES_TITLE} />
        {ranking.points.failure ? <MapRetry message="The state positions could not be loaded. Try again in a moment." onRetry={ranking.points.retry} className="mt-3" /> : null}
      </div>
      <div className={SIDE_PLACE} data-testid="map-states-side">
        <StatesSide ranking={ranking} />
      </div>
    </Figure>
  );
}
