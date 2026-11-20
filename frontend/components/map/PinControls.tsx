"use client";

import { useRef, useState, type KeyboardEvent } from "react";

import type { MapBox } from "@/components/map/basemap";
import type { PlacedPin } from "@/components/map/layout";
import { markBox, steppedKey } from "@/components/map/markPlacement";

export type PinControlProps = {
  pins: readonly PlacedPin[];
  frame: MapBox;
  selectedKey: string | null;
  onSelect: (key: string) => void;
  onHover?: (key: string | null) => void;
};

export function pinLabel(pin: PlacedPin): string {
  const count = pin.point.countText === undefined ? `${pin.point.total} ${pin.point.total === 1 ? "craft" : "crafts"}` : pin.point.countText;
  return count ? `${pin.point.name}, ${count}` : pin.point.name;
}

export function PinControls({ pins, frame, selectedKey, onSelect, onHover }: PinControlProps) {
  const [rover, setRover] = useState<string | null>(null);
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  const keys = pins.map((pin) => pin.point.key);
  const tabStop = rover !== null && keys.includes(rover) ? rover : (keys[0] ?? null);
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, key: string) => {
    if (event.key === "Escape") {
      onHover?.(null);
      return;
    }
    const next = steppedKey(keys, key, event.key);
    if (next === null) return;
    event.preventDefault();
    buttons.current.get(next)?.focus();
  };
  return (
    <div className="pointer-events-none absolute inset-0" role="group" aria-label="Places on the map" data-testid="map-pin-controls">
      {pins.map((pin) => (
        <button
          key={pin.point.key}
          ref={(node) => {
            if (node) buttons.current.set(pin.point.key, node);
            else buttons.current.delete(pin.point.key);
          }}
          type="button"
          tabIndex={pin.point.key === tabStop ? 0 : -1}
          aria-label={pinLabel(pin)}
          aria-pressed={pin.point.key === selectedKey}
          style={markBox({ x: pin.x, y: pin.y, r: pin.radius }, frame)}
          className="pointer-events-auto absolute aspect-square -translate-x-1/2 -translate-y-1/2 rounded-full border-0 bg-transparent p-0 pointer-coarse:min-w-11"
          onClick={() => onSelect(pin.point.key)}
          onKeyDown={(event) => onKeyDown(event, pin.point.key)}
          onFocus={() => {
            setRover(pin.point.key);
            onHover?.(pin.point.key);
          }}
          onBlur={() => onHover?.(null)}
          onPointerEnter={() => onHover?.(pin.point.key)}
          onPointerLeave={() => onHover?.(null)}
          data-testid="map-pin-control"
        />
      ))}
    </div>
  );
}
