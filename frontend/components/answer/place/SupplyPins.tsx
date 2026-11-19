"use client";

import { useMemo, useState } from "react";

import { AnswerFigure } from "@/components/answer/place/AnswerFigure";
import { AnswerMapSource } from "@/components/answer/place/AnswerMapSource";
import { IndiaMap } from "@/components/map/IndiaMap";
import type { MapPoint } from "@/components/map/layout";
import { listText } from "@/lib/format";
import type { PlacedOrigin } from "@/lib/supplyView";

export function supplyTitle(origins: readonly PlacedOrigin[]): string {
  return listText([...new Set(origins.map((origin) => origin.origin))]);
}

export function SupplyPins({ origins }: { origins: readonly PlacedOrigin[] }) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [pinned, setPinned] = useState<string | null>(null);
  const points = useMemo<MapPoint[]>(
    () =>
      origins.map((origin) => ({
        key: origin.key,
        name: origin.origin,
        latitude: origin.place.latitude,
        longitude: origin.place.longitude,
        total: 1,
        pinLabel: String(origin.place.pin),
        countText: origin.material,
        caption: null
      })),
    [origins]
  );
  const texts = { title: supplyTitle(origins), source: <AnswerMapSource boundary={null} districts={false} coordinates /> };
  return (
    <AnswerFigure texts={texts} data-testid="supply-pins">
      <IndiaMap points={points} hoveredKey={hovered} selectedKey={pinned} onHover={setHovered} onSelect={(key) => setPinned((current) => (current === key ? null : key))} />
    </AnswerFigure>
  );
}
