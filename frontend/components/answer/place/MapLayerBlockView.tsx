"use client";

import { useMemo, useState } from "react";

import { AnswerFigure, type FigureTable } from "@/components/answer/place/AnswerFigure";
import { AnswerMapSource } from "@/components/answer/place/AnswerMapSource";
import { MapPlaceholder } from "@/components/answer/place/MapPlaceholder";
import { DataTable } from "@/components/charts/DataTable";
import { DatasetCredit } from "@/components/DatasetCredit";
import { failureMessage } from "@/components/hooks/useRemote";
import { MapLegend, NO_READING_EXTRA, SALT_EXTRA, WATER_EXTRA, type LegendExtra } from "@/components/map/ChoroplethLegend";
import { DistrictFills, DistrictTag, SelectedDistrict } from "@/components/map/DistrictLayer";
import { MapCanvas } from "@/components/map/MapCanvas";
import { layerRows } from "@/components/map/MapLayerFigure";
import { MapRetry } from "@/components/map/MapRetry";
import { useLayerFill, useMapLayer, type DistrictName } from "@/components/map/MapLayerView";
import { RankedList, type RankedRow } from "@/components/map/RankedList";
import type { DistrictShape } from "@/components/map/shapeGeometry";
import type { MapLayerBlock } from "@/lib/explainerPlace";
import { layerColours, layerRamp } from "@/lib/mapRamps";
import { boundaryNote, isGone } from "@/lib/placeView";
import type { MapLayer } from "@/lib/regionContract";
import { districtReading, layerCaption, layerClassLabels, layerSummary } from "@/lib/regionView";

type Names = Map<number, DistrictName> | null;

const SERIES = { rain: "var(--series-rain)", heat: "var(--series-heat)", density: "var(--chart-series)" } as const;
const COLUMNS = [
  { key: "district", label: "District" },
  { key: "state", label: "State" },
  { key: "value", label: "Value", numeric: true }
];
const OUTLINED_EXTRA: LegendExtra = { key: "outlined", label: "Outlined: the districts this answer discusses", fill: "none", edge: "var(--map-selection)" };

function tagText(layer: MapLayer, names: Names, lgd: number): string {
  const name = names?.get(lgd)?.name;
  return name ? `${name} · ${districtReading(layer, lgd)}` : districtReading(layer, lgd);
}

function Readings({ layer, names, highlighted }: { layer: MapLayer; names: Names; highlighted: readonly number[] }) {
  if (highlighted.length === 0) return null;
  return (
    <dl className="grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-ink-1 font-ui text-ui font-normal sm:grid-cols-[repeat(2,minmax(0,1fr))] sm:gap-x-6" data-testid="map-layer-readings">
      {highlighted.map((lgd) => (
        <div key={lgd} className="flex min-w-0 items-baseline justify-between gap-3 border-b border-rule py-2">
          <dt className="min-w-0 break-words text-ink-2">{names?.get(lgd)?.name ?? "Outlined district"}</dt>
          <dd className="shrink-0 font-semibold text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]">{districtReading(layer, lgd)}</dd>
        </div>
      ))}
    </dl>
  );
}

function LayerMap({ layer, shapes, names, highlighted }: { layer: MapLayer; shapes: DistrictShape[]; names: Names; highlighted: readonly number[] }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const fillOf = useLayerFill(layer);
  const outlined = useMemo(() => shapes.filter((shape) => highlighted.includes(shape.lgd)), [shapes, highlighted]);
  const hoveredShape = hovered === null ? undefined : shapes.find((shape) => shape.lgd === hovered);
  const tagged = hoveredShape ? [hoveredShape] : outlined;
  return (
    <MapCanvas
      title={layer.layer.title}
      description={`${layerSummary(layer)} Districts are shaded by class; the districts this answer discusses are outlined.`}
      under={<DistrictFills shapes={shapes} fillOf={fillOf} onHover={setHovered} />}
      over={() => (
        <>
          {outlined.map((shape) => (
            <SelectedDistrict key={shape.lgd} shape={shape} />
          ))}
          <g className="max-sm:hidden">
            {tagged.map((shape) => (
              <DistrictTag key={shape.lgd} shape={shape} text={tagText(layer, names, shape.lgd)} />
            ))}
          </g>
        </>
      )}
    />
  );
}

function LayerSide({ layer, names, highlighted }: { layer: MapLayer; names: Names; highlighted: readonly number[] }) {
  const rows: RankedRow[] = layerRows(layer, names).map((row) => ({ key: String(row.lgd), name: row.name, value: row.value, display: districtReading(layer, row.lgd) }));
  const colours = layerColours(layer);
  const steps = layerClassLabels(layer).map((label, at) => ({ label, colour: colours[at] }));
  const emphKey = highlighted.length > 0 ? String(highlighted[0]) : null;
  return (
    <div className="grid min-w-0 content-start gap-5">
      <Readings layer={layer} names={names} highlighted={highlighted} />
      {rows.length ? <RankedList rows={rows} label={layer.layer.title} series={SERIES[layerRamp(layer.layer)]} emphKey={emphKey} all={{ label: `Show all ${rows.length}` }} /> : null}
      <MapLegend title={layer.layer.title} steps={steps} extras={[OUTLINED_EXTRA, NO_READING_EXTRA, SALT_EXTRA, WATER_EXTRA]} caption={layerCaption(layer)} summary={layerSummary(layer)} />
      <DatasetCredit dataset={layer.dataset} />
    </div>
  );
}

function valueTable(layer: MapLayer, names: Names): FigureTable | null {
  const rows = layerRows(layer, names).map((row) => ({ key: String(row.lgd), cells: { district: row.name, state: row.state, value: districtReading(layer, row.lgd) } }));
  return rows.length ? { node: <DataTable caption={layer.layer.title} columns={COLUMNS} rows={rows} />, count: rows.length } : null;
}

export function MapLayerBlockView({ block }: { block: MapLayerBlock }) {
  const data = useMapLayer(block.layer);
  const layer = data.layer.data;
  const shapes = data.shapes.data;
  const names = data.names.data;
  const table = useMemo(() => (layer ? valueTable(layer, names) : null), [layer, names]);
  if (isGone(data.layer.failure)) return null;
  const failure = data.layer.failure ?? data.shapes.failure;
  const texts = { title: block.title, dek: layer ? layerCaption(layer) : undefined, source: <AnswerMapSource boundary={boundaryNote(block.boundaryCaption, block.datasets)} /> };
  return (
    <AnswerFigure texts={texts} table={table} data-testid="map-layer-block" data-layer={block.layer}>
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,6.6fr)_minmax(0,4.4fr)] lg:items-start lg:gap-10">
        <div className="min-w-0">{layer && shapes ? <LayerMap layer={layer} shapes={shapes} names={names} highlighted={block.highlighted} /> : <MapPlaceholder />}</div>
        {failure ? (
          <MapRetry message={failureMessage(failure, "This layer could not be drawn. Try again in a moment.")} onRetry={data.layer.failure ? data.layer.retry : data.shapes.retry} />
        ) : layer ? (
          <LayerSide layer={layer} names={names} highlighted={block.highlighted} />
        ) : null}
      </div>
    </AnswerFigure>
  );
}
