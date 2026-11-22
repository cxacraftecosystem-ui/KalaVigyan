"use client";

import { useMemo, useState, type ReactNode } from "react";

import { DataTable, type DataRow } from "@/components/charts/DataTable";
import { DatasetCredit } from "@/components/DatasetCredit";
import { failureMessage } from "@/components/hooks/useRemote";
import { FOREIGN_EXTRA, MapLegend, NO_READING_EXTRA, SALT_EXTRA, WATER_EXTRA, type LegendExtra } from "@/components/map/ChoroplethLegend";
import { DistrictFills, DistrictTag, SelectedDistrict } from "@/components/map/DistrictLayer";
import { MapCanvas } from "@/components/map/MapCanvas";
import { MapRetry } from "@/components/map/MapRetry";
import { usePaletteFill, type DistrictName, type MapLayerData } from "@/components/map/MapLayerView";
import { MapSourceLine } from "@/components/map/MapSourceLine";
import { MarkControls } from "@/components/map/MarkControls";
import { PlaceMarkers, placeMapMarks } from "@/components/map/PlaceMarkers";
import { useMarkFocus } from "@/components/map/useStateRanking";
import { RankedList, type RankedRow } from "@/components/map/RankedList";
import type { DistrictShape } from "@/components/map/shapeGeometry";
import { Figure } from "@/components/ui/Figure";
import { Skeleton } from "@/components/ui/Skeleton";
import { markerFamilies, type PlaceMarker } from "@/lib/mapFamilies";
import { layerPalette, paletteSeries, paletteSteps } from "@/lib/mapPalettes";
import type { BoundaryNote, MapLayer } from "@/lib/regionContract";
import { districtReading, layerCaption, layerSummary } from "@/lib/regionView";

const PLACE_MARKS_LABEL = "Craft places on the map";
const COLUMNS = [
  { key: "district", label: "District" },
  { key: "state", label: "State" },
  { key: "value", label: "Value", numeric: true }
];

export type DistrictPick = { lgd: number | null; onPick: (lgd: number | null) => void };
type Names = Map<number, DistrictName> | null;

export function layerRows(layer: MapLayer, names: Names): { lgd: number; value: number; name: string; state: string }[] {
  if (!names) return [];
  return Object.entries(layer.values)
    .map(([lgd, value]) => ({ lgd: Number(lgd), value, named: names.get(Number(lgd)) }))
    .filter((row) => row.named !== undefined)
    .map((row) => ({ lgd: row.lgd, value: row.value, name: row.named?.name ?? "", state: row.named?.state ?? "" }))
    .sort((a, b) => b.value - a.value || a.name.localeCompare(b.name, "en"));
}

export function markerExtras(markers: readonly PlaceMarker[]): LegendExtra[] {
  const families = markerFamilies(markers).map((family) => ({ key: family.id, label: `${family.name} craft places`, fill: family.colour, disc: true }));
  return markers.some((marker) => marker.family === null) ? [...families, { key: "other-places", label: "Other craft places", fill: "var(--map-marker)", disc: true }] : families;
}

function LayerSide({ layer, names, markers, pick }: { layer: MapLayer; names: Names; markers: readonly PlaceMarker[]; pick: DistrictPick }) {
  const rows: RankedRow[] = layerRows(layer, names).map((row) => ({ key: String(row.lgd), name: row.name, value: row.value, display: districtReading(layer, row.lgd), onPick: () => pick.onPick(row.lgd) }));
  const palette = layerPalette(layer.layer);
  const steps = paletteSteps(layer);
  return (
    <div className="grid gap-[18px]">
      {rows.length ? <RankedList rows={rows} label={layer.layer.title} series={paletteSeries(palette)} all={{ label: `Show all ${rows.length}` }} /> : null}
      <MapLegend title={layer.layer.title} steps={steps} extras={[NO_READING_EXTRA, SALT_EXTRA, FOREIGN_EXTRA, WATER_EXTRA, ...markerExtras(markers)]} caption={layerCaption(layer)} summary={layerSummary(layer)} />
      <DatasetCredit dataset={layer.dataset} />
    </div>
  );
}

function tagText(layer: MapLayer, names: Names, lgd: number): string {
  const name = names?.get(lgd)?.name;
  const reading = districtReading(layer, lgd);
  return name ? `${name} · ${reading}` : reading;
}

function LayerMap({ layer, shapes, names, markers, pick }: { layer: MapLayer; shapes: DistrictShape[]; names: Names; markers: readonly PlaceMarker[]; pick: DistrictPick }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const focus = useMarkFocus();
  const fillOf = usePaletteFill(layer);
  const select = (lgd: number) => pick.onPick(pick.lgd === lgd ? null : lgd);
  const active = hovered ?? pick.lgd;
  const activeShape = active === null ? undefined : shapes.find((shape) => shape.lgd === active);
  const picked = pick.lgd === null ? undefined : shapes.find((shape) => shape.lgd === pick.lgd);
  return (
    <MapCanvas
      title={layer.layer.title}
      description={`${layerSummary(layer)} Districts are shaded by class; craft places are marked as discs.`}
      under={<DistrictFills shapes={shapes} fillOf={fillOf} onHover={setHovered} onSelect={select} />}
      over={(scene) => (
        <>
          {picked ? <SelectedDistrict shape={picked} /> : null}
          <PlaceMarkers markers={markers} scene={scene} active={focus.active} />
          {activeShape ? <DistrictTag shape={activeShape} text={tagText(layer, names, activeShape.lgd)} /> : null}
        </>
      )}
      controls={(scene) => (markers.length ? <MarkControls marks={placeMapMarks(markers, scene.scale)} scene={scene} focus={focus} label={PLACE_MARKS_LABEL} /> : null)}
    />
  );
}

function districtTable(layer: MapLayer, names: Names): { rows: DataRow[]; table: ReactNode } {
  const rows = layerRows(layer, names).map((row) => ({ key: String(row.lgd), cells: { district: row.name, state: row.state, value: districtReading(layer, row.lgd) } }));
  return { rows, table: rows.length ? <DataTable caption={layer.layer.title} columns={COLUMNS} rows={rows} /> : undefined };
}

export function MapLayerFigure({ data, markers, boundary, pick, controls }: { data: MapLayerData; markers: readonly PlaceMarker[]; boundary: BoundaryNote | null; pick: DistrictPick; controls?: ReactNode }) {
  const layer = data.layer.data;
  const shapes = data.shapes.data;
  const names = data.names.data;
  const shown = useMemo(() => (layer ? districtTable(layer, names) : null), [layer, names]);
  const failure = data.layer.failure ?? data.shapes.failure;
  return (
    <Figure number={1} kind="map" id="map-figure" title={layer?.layer.title ?? "District values"} dek={layer ? layerCaption(layer) : undefined} source={<MapSourceLine caption={boundary?.caption ?? null} counts={false} />} table={shown?.table} valueCount={shown?.rows.length}>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,6.6fr)_minmax(0,4.4fr)] lg:items-start lg:gap-12">
        <div className="min-w-0">{layer && shapes ? <LayerMap layer={layer} shapes={shapes} names={names} markers={markers} pick={pick} /> : <Skeleton shape="chart" label="Drawing the district values" />}</div>
        <div className="grid content-start gap-[18px]">
          {controls}
          {failure ? (
            <MapRetry message={failureMessage(failure, "This layer could not be drawn. Try again in a moment.")} onRetry={data.layer.failure ? data.layer.retry : data.shapes.retry} />
          ) : layer ? (
            <LayerSide layer={layer} names={names} markers={markers} pick={pick} />
          ) : null}
        </div>
      </div>
    </Figure>
  );
}
