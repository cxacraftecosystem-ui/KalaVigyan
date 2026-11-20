"use client";

import { useId, useMemo, useRef } from "react";

import { fitStyle, useFitScale } from "@/components/charts/useFitScale";
import { indiaOutlinePath, project, VIEW_BOX } from "@/components/map/projection";
import { GeneralFigure, type RenderUnit } from "@/components/monograph/kinds/general/GeneralFigure";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { mapLayerSpecShape, parsedSpec, placeRadius, type MapPlace } from "@/lib/componentSpecsGeneral";

import "./general.css";

const LABEL_SIZE = "calc(var(--text-caption) * var(--k, 1))";
const HALO_WIDTH = "calc(3px * var(--k, 1))";
const LABEL_GAP = 4;

export function largestValue(places: readonly MapPlace[]): number {
  return Math.max(0, ...places.map((place) => place.value ?? 0));
}

function PlaceMap({ places, labelledBy }: { places: MapPlace[]; labelledBy: string }) {
  const ref = useRef<SVGSVGElement | null>(null);
  const scale = useFitScale(ref, VIEW_BOX.width);
  const largest = largestValue(places);
  return (
    <svg ref={ref} viewBox={`0 0 ${VIEW_BOX.width} ${VIEW_BOX.height}`} role="img" aria-labelledby={labelledBy} data-fit="" className="block h-auto w-full [forced-color-adjust:none]" style={fitStyle(scale)} data-testid="general-map">
      <path d={indiaOutlinePath()} fillRule="evenodd" fill="var(--map-land)" stroke="var(--map-coast)" strokeWidth={1.2} vectorEffect="non-scaling-stroke" />
      {places.map((place, at) => {
        const { x, y } = project(place.longitude, place.latitude);
        const radius = placeRadius(place.value, largest) * scale;
        return (
          <g key={place.reading}>
            <circle cx={x} cy={y} r={radius} fill={place.value === null ? "var(--map-marker)" : "var(--chart-series)"} fillOpacity={place.value === null ? 1 : 0.85} stroke="var(--map-marker-ring)" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
            <text x={x + radius + LABEL_GAP * scale} y={y} dominantBaseline="central" fill="var(--map-label)" stroke="var(--map-label-halo)" strokeLinejoin="round" paintOrder="stroke" style={{ fontSize: LABEL_SIZE, strokeWidth: HALO_WIDTH }}>
              {at + 1}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function PlaceList({ places, valueLabel, renderUnit }: { places: MapPlace[]; valueLabel: string | null; renderUnit: RenderUnit }) {
  return (
    <div className="grid content-start gap-2">
      {valueLabel ? <p className="font-ui text-caption text-ink-3">{renderUnit(valueLabel)}</p> : null}
      <ol className="grid" data-testid="general-places">
        {places.map((place, at) => (
          <li key={place.reading} className="grid grid-cols-[1.75rem_minmax(0,1fr)] gap-2 border-t border-rule py-2">
            <span className="font-ui text-label text-ink-2 [font-variant-numeric:lining-nums_tabular-nums]">{at + 1}</span>
            <div className="grid min-w-0 gap-0.5">
              <p className="font-ui text-ui font-medium text-ink-1">{renderUnit(place.name)}</p>
              <p className="font-reading text-body-sm text-ink-1">{renderUnit(place.reading)}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function MapLayerView({ spec, renderUnit }: ComponentViewProps) {
  const layer = useMemo(() => parsedSpec(mapLayerSpecShape, spec), [spec]);
  const titleId = useId();
  if (!layer) return null;
  return (
    <GeneralFigure kind="general_map_layer" head={layer.head} titleId={titleId} renderUnit={renderUnit}>
      <div className="grid gap-5 md:grid-cols-[minmax(0,1.25fr)_minmax(15rem,1fr)] md:items-start">
        <PlaceMap places={layer.places} labelledBy={titleId} />
        <PlaceList places={layer.places} valueLabel={layer.valueLabel} renderUnit={renderUnit} />
      </div>
    </GeneralFigure>
  );
}
