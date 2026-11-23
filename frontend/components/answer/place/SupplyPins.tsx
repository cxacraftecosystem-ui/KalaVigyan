"use client";

import { useMemo, useState } from "react";

import { AnswerFigure } from "@/components/answer/place/AnswerFigure";
import { AnswerMapSource } from "@/components/answer/place/AnswerMapSource";
import { IndiaMap } from "@/components/map/IndiaMap";
import { useOutlineCaption } from "@/components/map/useOutlineCaption";
import type { MapPoint } from "@/components/map/layout";
import { listText } from "@/lib/format";
import type { BoundaryNote, RegionDataset } from "@/lib/regionContract";
import type { SupplyPin } from "@/lib/supplyView";

export function supplyTitle(pins: readonly SupplyPin[]): string {
  return listText(pins.map((pin) => pin.origin));
}

export function districtCredit(pins: readonly SupplyPin[], boundary: RegionDataset | null, caption: string | null): BoundaryNote | null {
  return boundary !== null && pins.some((pin) => pin.byDistrict) ? { caption: caption ?? "", dataset: boundary } : null;
}

export function SupplyPins({ pins, boundary = null }: { pins: readonly SupplyPin[]; boundary?: RegionDataset | null }) {
  const [hovered, setHovered] = useState<string | null>(null);
  const outline = useOutlineCaption();
  const [pinned, setPinned] = useState<string | null>(null);
  const points = useMemo<MapPoint[]>(
    () =>
      pins.map((pin) => ({
        key: pin.key,
        name: pin.origin,
        latitude: pin.latitude,
        longitude: pin.longitude,
        total: 1,
        pinLabel: String(pin.pin),
        countText: pin.materials,
        caption: null
      })),
    [pins]
  );
  const wikidata = pins.some((pin) => !pin.byDistrict);
  const texts = { title: supplyTitle(pins), source: <AnswerMapSource boundary={districtCredit(pins, boundary, outline)} caption={outline} coordinates={wikidata} /> };
  return (
    <AnswerFigure texts={texts} data-testid="supply-pins">
      <IndiaMap points={points} hoveredKey={hovered} selectedKey={pinned} onHover={setHovered} onSelect={(key) => setPinned((current) => (current === key ? null : key))} />
    </AnswerFigure>
  );
}
