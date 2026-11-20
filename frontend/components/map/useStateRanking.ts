"use client";

import { useMemo, useState } from "react";

import { useRemote, type Remote } from "@/components/hooks/useRemote";
import type { MarkFocus } from "@/components/map/MarkControls";
import type { MapMark } from "@/components/map/markPlacement";
import type { RankedRow } from "@/components/map/RankedList";
import { placedCircles, stateMapMarks, type PlacedCircle } from "@/components/map/StateCircles";
import { listCounts, searchHref, stateCrafts, type StateCounts, type StateCrafts } from "@/lib/atlasIndex";
import { useCraftCatalogue } from "@/lib/craftCatalogue";
import type { CraftCatalogue } from "@/lib/craftCatalogueContract";
import { fetchCraftMapPoints } from "@/lib/craftRegion";
import { stateMarks } from "@/lib/mapStates";
import type { CraftMapPoint } from "@/lib/types";

export type StateRanking = {
  catalogue: CraftCatalogue | null;
  points: Remote<CraftMapPoint[]>;
  counts: StateCounts | null;
  lists: StateCrafts | null;
  circles: PlacedCircle[];
  marks: MapMark[];
  rows: RankedRow[];
  catalogueError: string | null;
  reloadCatalogue: () => void;
};

export function rankedStateRows(counts: StateCounts): RankedRow[] {
  return counts.states.map((state) => ({ key: state.name, name: state.name, value: state.count, href: searchHref(state.name) }));
}

export function useStateRanking(initial: CraftCatalogue | null = null): StateRanking {
  const { catalogue: loaded, error, reload } = useCraftCatalogue();
  const catalogue = loaded ?? initial;
  const points = useRemote(fetchCraftMapPoints);
  const lists = useMemo(() => (catalogue ? stateCrafts(catalogue) : null), [catalogue]);
  const counts = useMemo(() => (lists ? listCounts(lists) : null), [lists]);
  const circles = useMemo(() => (counts && points.data ? placedCircles(stateMarks(counts.states, points.data)) : []), [counts, points.data]);
  const marks = useMemo(() => (lists ? stateMapMarks(circles, lists.states) : []), [circles, lists]);
  const rows = useMemo(() => (counts ? rankedStateRows(counts) : []), [counts]);
  return { catalogue, points, counts, lists, circles, marks, rows, catalogueError: error, reloadCatalogue: reload };
}

export function useMarkFocus(): MarkFocus {
  const [active, setActive] = useState<string | null>(null);
  return { active, onActive: setActive };
}
