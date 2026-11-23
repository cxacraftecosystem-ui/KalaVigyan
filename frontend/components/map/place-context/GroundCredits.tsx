import { DataTable, type DataColumn, type DataRow } from "@/components/charts/DataTable";
import { DatasetCredit } from "@/components/DatasetCredit";
import { safeOutboundUrl } from "@/lib/citations";
import { formatNumber } from "@/lib/measure";
import type { CraftGround, GroundLayer, GroundPin, GroundRiver } from "@/lib/placeGround";
import { commodityWord, elevationText, LAYER_SHORT } from "@/lib/placeGroundView";
import type { RegionDataset } from "@/lib/regionContract";
import { wikidataUrl } from "@/lib/supplyView";
import type { SourceRef } from "@/lib/types";

export type CreditedMarks = { abroad: readonly GroundPin[]; rivers: readonly GroundRiver[] };
type CreditsProps = { layers: readonly GroundLayer[]; datasets: readonly RegionDataset[]; sources: readonly SourceRef[]; marks?: CreditedMarks };

export const WIKIDATA_LICENCE = "CC0";
const NO_MARKS: CreditedMarks = { abroad: [], rivers: [] };

const LINK = "kv-link font-normal";

export function LayerCredit({ layer }: { layer: GroundLayer }) {
  const href = safeOutboundUrl(layer.url);
  return (
    <span className="grid gap-0.5 font-ui text-caption text-ink-3" data-testid="layer-credit">
      <span>
        {href ? (
          <a href={href} target="_blank" rel="noopener noreferrer" className={LINK}>
            {layer.title}
          </a>
        ) : (
          <span className="font-medium text-ink-2">{layer.title}</span>
        )}
        {` · ${layer.publisher} · ${layer.edition} · ${layer.licence}`}
      </span>
      {layer.citation ? <span>{layer.citation}</span> : null}
    </span>
  );
}

export function PlaceSource({ source }: { source: SourceRef }) {
  const href = safeOutboundUrl(source.url);
  const title = [source.title, source.year].filter(Boolean).join(", ");
  return (
    <span className="font-ui text-caption text-ink-3" data-testid="place-source">
      {"Placed by "}
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer" className={LINK}>
          {title}
        </a>
      ) : (
        title
      )}
    </span>
  );
}

export function AbroadSource({ pin }: { pin: GroundPin }) {
  const href = safeOutboundUrl(wikidataUrl(pin.wikidataId));
  const item = `Wikidata ${pin.wikidataId}`;
  return (
    <span className="font-ui text-caption text-ink-3" data-testid="abroad-source">
      {`${pin.name} placed by `}
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer" className={LINK}>
          {item}
        </a>
      ) : (
        item
      )}
      {` · ${WIKIDATA_LICENCE}`}
    </span>
  );
}

export function creditedDatasets(datasets: readonly RegionDataset[], rivers: readonly GroundRiver[]): RegionDataset[] {
  const credited = new Map(datasets.map((dataset) => [dataset.code, dataset]));
  for (const river of rivers) for (const dataset of [river.hydrorivers, river.names]) if (!credited.has(dataset.code)) credited.set(dataset.code, dataset);
  return [...credited.values()];
}

export function GroundCredits({ layers, datasets, sources, marks = NO_MARKS }: CreditsProps) {
  return (
    <div className="mt-3 grid gap-2 border-t border-rule pt-3 md:grid-cols-2 md:gap-x-8" data-testid="ground-credits">
      {layers.map((layer) => (
        <LayerCredit key={layer.key} layer={layer} />
      ))}
      {creditedDatasets(datasets, marks.rivers).map((dataset) => (
        <DatasetCredit key={dataset.code} dataset={dataset} />
      ))}
      {sources.map((source) => (
        <PlaceSource key={source.id} source={source} />
      ))}
      {marks.abroad.map((pin) => (
        <AbroadSource key={pin.key} pin={pin} />
      ))}
    </div>
  );
}

const PLACE_COLUMNS: readonly DataColumn[] = [
  { key: "place", label: "Place" },
  { key: "elevation", label: "Elevation" },
  { key: "river", label: "River, km", numeric: true },
  { key: "lake", label: "Lake, km", numeric: true },
  { key: "deposits", label: "Deposits", numeric: true }
];

const DEPOSIT_COLUMNS: readonly DataColumn[] = [
  { key: "site", label: "Site" },
  { key: "commodities", label: "Commodities" },
  { key: "status", label: "Status" },
  { key: "distance", label: "Nearest place, km", numeric: true },
  { key: "named", label: "Named by a material" }
];

function placeRows(ground: CraftGround): DataRow[] {
  return ground.places.map((place) => ({
    key: place.key,
    cells: {
      place: place.name,
      elevation: elevationText(place.ground.elevation),
      river: place.ground.river ? formatNumber(place.ground.river.distanceKm) : "",
      lake: place.ground.lake ? formatNumber(place.ground.lake.distanceKm) : "",
      deposits: formatNumber(place.ground.depositClasses.reduce((sum, tally) => sum + tally.count, 0), 0)
    }
  }));
}

function depositRows(ground: CraftGround): DataRow[] {
  return ground.deposits.map((deposit) => ({
    key: String(deposit.depId),
    cells: {
      site: deposit.name || `MRDS ${deposit.depId}`,
      commodities: deposit.commodities.split(",").map((name) => commodityWord(name.trim())).join(", "),
      status: deposit.status,
      distance: formatNumber(deposit.nearestKm),
      named: deposit.matched ? "Yes" : "No"
    }
  }));
}

export function groundValueCount(ground: CraftGround): number {
  return ground.places.length + ground.deposits.length;
}

export function GroundTables({ ground }: { ground: CraftGround }) {
  return (
    <div className="grid gap-6" data-testid="ground-tables">
      <DataTable caption={`The ground at each place, measured from ${LAYER_SHORT.ETOPO1}, Natural Earth and ${LAYER_SHORT.USGS_MRDS}`} columns={PLACE_COLUMNS} rows={placeRows(ground)} />
      {ground.deposits.length ? <DataTable caption={`Mineral deposits within ${ground.radiusKm} km of a place`} columns={DEPOSIT_COLUMNS} rows={depositRows(ground)} /> : null}
    </div>
  );
}
