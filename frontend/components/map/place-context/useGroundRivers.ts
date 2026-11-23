"use client";

import { useCallback, useMemo } from "react";

import { useRemote } from "@/components/hooks/useRemote";
import { inFrame } from "@/lib/groundFrame";
import type { GroundFrame, GroundRiver } from "@/lib/placeGround";
import { fetchRiverBasin, type LonLat, type RiverBasin } from "@/lib/riverTopology";

export type DrawnRiver = { river: GroundRiver; lines: LonLat[][] };

const NO_RIVERS: readonly GroundRiver[] = [];
const NONE_DRAWN: readonly DrawnRiver[] = [];

export function drawnRivers(rivers: readonly GroundRiver[], basins: ReadonlyMap<number, RiverBasin>, frame: GroundFrame): DrawnRiver[] {
  return rivers.flatMap((river) => {
    const reaches = basins.get(river.mainRiv)?.reaches;
    const lines = river.reachIds.flatMap((id) => {
      const reach = reaches?.get(id);
      return reach ? [reach.line] : [];
    });
    const shown = lines.length === river.reachIds.length && lines.some((line) => line.some((point) => inFrame(frame, point)));
    return shown ? [{ river, lines }] : [];
  });
}

async function basinsOf(mainRivs: readonly number[]): Promise<Map<number, RiverBasin>> {
  const basins = await Promise.all(mainRivs.map(fetchRiverBasin));
  return new Map(basins.map((basin) => [basin.mainRiv, basin]));
}

export function useGroundRivers(rivers: readonly GroundRiver[] | undefined, frame: GroundFrame): readonly DrawnRiver[] {
  const listed = rivers ?? NO_RIVERS;
  const wanted = [...new Set(listed.map((river) => river.mainRiv))].sort((a, b) => a - b).join(" ");
  const load = useCallback(() => basinsOf(wanted.split(" ").map(Number)), [wanted]);
  const basins = useRemote(wanted ? load : null);
  return useMemo(() => (basins.data ? drawnRivers(listed, basins.data, frame) : NONE_DRAWN), [basins.data, listed, frame]);
}
