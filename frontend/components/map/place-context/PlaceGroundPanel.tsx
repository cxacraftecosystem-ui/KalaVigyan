"use client";

import { useId, useMemo } from "react";

import { useRemote } from "@/components/hooks/useRemote";
import { GroundFacts } from "@/components/map/place-context/GroundFacts";
import { Skeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import { mapGroundPath, parseMapPlaceGround, type MapPlaceGround } from "@/lib/placeGround";

export const GROUND_HEADING = "The ground here";

export async function fetchMapGround(longitude: number, latitude: number): Promise<MapPlaceGround> {
  return parseMapPlaceGround(await apiFetch<unknown>(mapGroundPath(longitude, latitude)));
}

export function PlaceGroundView({ ground, headingId }: { ground: MapPlaceGround; headingId: string }) {
  return (
    <section className="grid gap-2 border-t border-ink-1 pt-3" aria-labelledby={headingId} data-testid="map-place-ground">
      <h3 id={headingId} className="kicker">
        {GROUND_HEADING}
      </h3>
      {ground.district ? <p className="font-ui text-label text-ink-2">{`${ground.district} district`}</p> : null}
      <GroundFacts at={ground.ground} radiusKm={ground.radiusKm} layers={ground.layers} datasets={ground.datasets} classes={ground.classes} />
    </section>
  );
}

export function PlaceGroundPanel({ longitude, latitude }: { longitude: number; latitude: number }) {
  const headingId = useId();
  const load = useMemo(() => () => fetchMapGround(longitude, latitude), [longitude, latitude]);
  const ground = useRemote(load);
  if (ground.failure) return null;
  if (!ground.data) return <Skeleton shape="lede" label="Measuring the ground here" />;
  return <PlaceGroundView ground={ground.data} headingId={headingId} />;
}
