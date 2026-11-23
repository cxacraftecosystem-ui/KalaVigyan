"use client";

import { useMemo, useRef, useState } from "react";

import { inFrame } from "@/components/answer/journey/journeyGeometry";
import { AnswerFigure } from "@/components/answer/place/AnswerFigure";
import { AnswerMapSource } from "@/components/answer/place/AnswerMapSource";
import { PIN_DISC } from "@/components/answer/place/figureMarks";
import { fitStyle, useFitScale } from "@/components/charts/useFitScale";
import { AbroadInset, type InsetPin, type InsetRoute } from "@/components/map/AbroadInset";
import { IndiaMap, type MapPoint } from "@/components/map/IndiaMap";
import { VIEW_BOX } from "@/components/map/projection";
import { listText } from "@/lib/format";
import type { BoundaryNote } from "@/lib/regionContract";
import { wikidataUrl } from "@/lib/supplyView";
import { abroadSummary, type PlacedPlace, type TimelineRouteLine } from "@/lib/timelineView";

function RouteLines({ routes }: { routes: readonly TimelineRouteLine[] }) {
  return (
    <g className="pointer-events-none" data-testid="timeline-routes">
      {routes.map((route) => {
        const from = inFrame(route.start.longitude, route.start.latitude);
        const to = inFrame(route.end.longitude, route.end.latitude);
        return (
          <g key={route.key} data-testid="timeline-route">
            <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="var(--map-label-halo)" strokeWidth={6} strokeLinecap="round" vectorEffect="non-scaling-stroke" />
            <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="var(--terracotta)" strokeWidth={2.5} strokeLinecap="round" vectorEffect="non-scaling-stroke" />
            <circle cx={to.x} cy={to.y} r={7} fill="var(--map-marker)" stroke="var(--map-marker-ring)" strokeWidth={2} />
          </g>
        );
      })}
    </g>
  );
}

function Abroad({ places, routes }: { places: readonly PlacedPlace[]; routes: readonly TimelineRouteLine[] }) {
  const pins = useMemo<InsetPin[]>(() => places.map((place) => ({ key: `abroad:${place.index}`, label: String(place.pin), name: place.name, longitude: place.longitude, latitude: place.latitude })), [places]);
  const lines = useMemo<InsetRoute[]>(
    () => routes.filter((route) => route.start.beyond || route.end.beyond).map((route) => ({ key: route.key, from: route.start, to: route.end })),
    [routes]
  );
  const summary = abroadSummary(places);
  return (
    <div className="mt-3 grid min-w-0 gap-1.5 lg:max-w-md" dir="ltr" data-testid="timeline-abroad-frame">
      <AbroadInset pins={pins} routes={lines} label={summary} />
      <p className="font-ui text-caption text-ink-3">{summary}</p>
    </div>
  );
}

function PlaceLinks({ placed }: { placed: readonly PlacedPlace[] }) {
  return (
    <ul className="mt-3 flex min-w-0 flex-wrap gap-x-4 gap-y-1.5 font-ui text-ui font-normal" aria-label="Places on the map" data-testid="timeline-places">
      {placed.map((place) => (
        <li key={place.index} className="inline-flex min-w-0 items-center gap-1.5">
          <span className={PIN_DISC}>{place.pin}</span>
          <span className="min-w-0 break-words text-ink-1">{place.name}</span>
          {place.wikidataId ? (
            <a href={wikidataUrl(place.wikidataId)} target="_blank" rel="noopener noreferrer" className="kv-link font-ui text-caption">
              Wikidata
              <span className="sr-only"> for {place.name} (opens in a new tab)</span>
            </a>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

type PinsProps = { placed: readonly PlacedPlace[]; reached: ReadonlySet<number>; routes: readonly TimelineRouteLine[]; boundary: BoundaryNote | null };

export function TimelinePins({ placed, reached, routes, boundary }: PinsProps) {
  const frame = useRef<HTMLDivElement | null>(null);
  const scale = useFitScale(frame, VIEW_BOX.width);
  const [hovered, setHovered] = useState<string | null>(null);
  const [pinned, setPinned] = useState<string | null>(null);
  const shown = useMemo(() => placed.filter((place) => reached.has(place.index)), [placed, reached]);
  const points = useMemo<MapPoint[]>(
    () =>
      shown
        .filter((place) => !place.beyond)
        .map((place) => ({ key: `place:${place.index}`, name: place.name, latitude: place.latitude, longitude: place.longitude, total: 1, pinLabel: String(place.pin), caption: null })),
    [shown]
  );
  const abroad = useMemo(() => shown.filter((place) => place.beyond), [shown]);
  const overlay = <RouteLines routes={routes} />;
  const texts = { title: listText(placed.map((place) => place.name)), source: <AnswerMapSource boundary={boundary} coordinates /> };
  return (
    <AnswerFigure texts={texts} className="lg:sticky lg:top-24" data-testid="timeline-pins">
      <div ref={frame} style={fitStyle(scale)} className="min-w-0">
        <IndiaMap points={points} hoveredKey={hovered} selectedKey={pinned} onHover={setHovered} onSelect={(key) => setPinned((current) => (current === key ? null : key))} overlay={overlay} />
      </div>
      {abroad.length > 0 ? <Abroad places={abroad} routes={routes} /> : null}
      <PlaceLinks placed={placed} />
    </AnswerFigure>
  );
}
