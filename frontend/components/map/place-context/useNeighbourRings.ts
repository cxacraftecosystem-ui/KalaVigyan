"use client";

import { useEffect, useState } from "react";

import { decodeRings, NEIGHBOURS_ASSET, type NeighbourFile } from "@/components/map/basemap";
import type { Ring } from "@/components/map/indiaGeometry";

let pending: Promise<Ring[]> | null = null;

export function neighbourRings(file: Pick<NeighbourFile, "countries">): Ring[] {
  return file.countries.flatMap((country) => decodeRings(country.rings));
}

function loadNeighbourRings(): Promise<Ring[]> {
  if (pending) return pending;
  const loading = fetch(NEIGHBOURS_ASSET, { cache: "force-cache" }).then((response) => {
    if (!response.ok) throw new Error(`${NEIGHBOURS_ASSET} returned ${response.status}`);
    return response.json().then((file: NeighbourFile) => neighbourRings(file));
  });
  pending = loading;
  loading.catch(() => {
    pending = null;
  });
  return loading;
}

export function useNeighbourRings(): Ring[] {
  const [rings, setRings] = useState<Ring[]>([]);
  useEffect(() => {
    let cancelled = false;
    loadNeighbourRings().then(
      (loaded) => {
        if (!cancelled) setRings(loaded);
      },
      () => undefined
    );
    return () => {
      cancelled = true;
    };
  }, []);
  return rings;
}
