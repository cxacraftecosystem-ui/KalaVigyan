"use client";

import { useId, useState, type ReactNode } from "react";

import { GroundCredits, GroundTables, groundValueCount, PlaceSource } from "@/components/map/place-context/GroundCredits";
import { GroundFacts, type NotesFor } from "@/components/map/place-context/GroundFacts";
import { GroundLegend } from "@/components/map/place-context/GroundLegend";
import { GroundMap, type MapPin } from "@/components/map/place-context/GroundMap";
import { TextLink } from "@/components/ui/TextLink";
import type { CraftGround, GroundNote, GroundPlace } from "@/lib/placeGround";
import { frameDek, listText, materialSentence, notesFor, placeLine, placesTitle } from "@/lib/placeGroundView";

import "./placeContext.css";

export const PLACES_SHOWN = 4;
export const PLACED_LABEL = "Where the craft is practised";
export const MAP_KICKER = "Map";

export type RenderUnit = (ref: string) => ReactNode;
export type GroundFigureProps = { ground: CraftGround; notes?: readonly GroundNote[]; renderUnit?: RenderUnit };

const NUMBER_BADGE = "inline-grid h-6 w-6 shrink-0 place-items-center rounded-full bg-sunk font-ui text-label text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]";

export function mapPins(places: readonly GroundPlace[]): MapPin[] {
  return places.map((place, at) => ({ key: place.key, label: places.length === 1 ? place.name : String(at + 1), longitude: place.longitude, latitude: place.latitude }));
}

function notesWriter(notes: readonly GroundNote[], renderUnit: RenderUnit | undefined): NotesFor | undefined {
  if (!renderUnit || !notes.length) return undefined;
  return (reading) => {
    const units = notesFor(notes, reading);
    return units.length ? units.map((unit) => <span key={unit}>{renderUnit(unit)} </span>) : null;
  };
}

function Materials({ place, radiusKm }: { place: GroundPlace; radiusKm: number }) {
  if (!place.materials.length) return null;
  return (
    <ul className="grid gap-2.5 border-t border-rule pt-3" data-testid="ground-materials">
      {place.materials.map((match) => (
        <li key={match.material} className="grid gap-0.5">
          <span className="font-ui text-label text-ink-3">{match.material}</span>
          <span className="font-reading text-body-sm text-ink-1">{materialSentence(match, radiusKm, place.name)}</span>
        </li>
      ))}
    </ul>
  );
}

type CardProps = { ground: CraftGround; place: GroundPlace; number: number | null; notes?: NotesFor };

function PlaceCard({ ground, place, number, notes }: CardProps) {
  const source = ground.sources.find((found) => found.id === place.sourceId);
  return (
    <article className="grid min-w-0 gap-3" data-testid="ground-place">
      <header className="grid gap-1">
        <p className="flex items-center gap-2 font-ui text-h4 text-ink-1">
          {number !== null ? <span className={NUMBER_BADGE}>{number}</span> : null}
          <span className="min-w-0 break-words">{place.name}</span>
        </p>
        <p className="font-ui text-label text-ink-2">{placeLine(place)}</p>
        {source ? <PlaceSource source={source} /> : null}
      </header>
      <GroundFacts at={place.ground} radiusKm={ground.radiusKm} layers={ground.layers} datasets={ground.datasets} classes={ground.classes} notes={notes} />
      <Materials place={place} radiusKm={ground.radiusKm} />
    </article>
  );
}

function Places({ ground, notes }: { ground: CraftGround; notes?: NotesFor }) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  const many = ground.places.length > 1;
  const shown = open ? ground.places : ground.places.slice(0, PLACES_SHOWN);
  return (
    <div className="grid min-w-0 content-start gap-8">
      {ground.soilMaterials.length ? (
        <p className="grid gap-0.5 border-t border-ink-1 pt-3" data-testid="ground-earths">
          <span className="font-ui text-label text-ink-3">Clays and earths the craft works</span>
          <span className="font-reading text-body-sm text-ink-1">{listText(ground.soilMaterials)}</span>
        </p>
      ) : null}
      <div id={listId} className="grid gap-8">
        {shown.map((place, at) => (
          <PlaceCard key={place.key} ground={ground} place={place} number={many ? at + 1 : null} notes={at === 0 ? notes : undefined} />
        ))}
      </div>
      {ground.places.length > PLACES_SHOWN ? (
        <p>
          <TextLink onClick={() => setOpen((value) => !value)} expanded={open} controls={listId} standalone>
            {open ? `Show the first ${PLACES_SHOWN} places` : `Show all ${ground.places.length} places`}
          </TextLink>
        </p>
      ) : null}
    </div>
  );
}

export function GroundFigure({ ground, notes = [], renderUnit }: GroundFigureProps) {
  const title = placesTitle(ground.places);
  const dek = frameDek(ground.radiusKm, ground.places.length);
  const values = groundValueCount(ground);
  return (
    <figure className="kv-figure" data-testid="why-here" data-places={ground.places.length}>
      <figcaption className="grid gap-1.5">
        <p className="kv-fig-no">{MAP_KICKER}</p>
        <p className="max-w-measure font-reading text-h3 text-ink-1">{title}</p>
        <p className="max-w-measure font-ui text-ui font-normal text-ink-2">{dek}</p>
      </figcaption>
      <div className="mt-5 grid gap-8 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:items-start lg:gap-12">
        <div className="grid min-w-0 gap-4">
          <GroundMap frame={ground.frame} pins={mapPins(ground.places)} deposits={ground.deposits} radiusKm={ground.radiusKm} title={title} description={dek} />
          <GroundLegend frame={ground.frame} deposits={ground.deposits} classes={ground.classes} radiusKm={ground.radiusKm} placed={PLACED_LABEL} />
        </div>
        <Places ground={ground} notes={notesWriter(notes, renderUnit)} />
      </div>
      <GroundCredits layers={ground.layers} datasets={ground.datasets} sources={ground.sources} />
      <details className="mt-2 min-w-0">
        <summary className="kv-link inline-flex min-h-target cursor-pointer items-center font-ui text-ui">{`All ${values} values`}</summary>
        <div className="overflow-x-auto pt-2">
          <GroundTables ground={ground} />
        </div>
      </details>
    </figure>
  );
}
