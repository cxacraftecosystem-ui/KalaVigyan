"use client";

import { useRef, useState, type KeyboardEvent } from "react";

import type { MapScene } from "@/components/map/MapCanvas";
import { MarkCard } from "@/components/map/MarkCard";
import { MarkPanel, panelSurface, type PanelSurface } from "@/components/map/MarkPanel";
import { markBox, markLabel, steppedKey, type MapMark } from "@/components/map/markPlacement";

export type MarkFocus = { active: string | null; onActive: (key: string | null) => void };

const BUTTON =
  "pointer-events-auto absolute aspect-square -translate-x-1/2 -translate-y-1/2 rounded-full border-0 bg-transparent p-0 pointer-coarse:min-w-11";

export function MarkControls({ marks, scene, focus, label }: { marks: readonly MapMark[]; scene: MapScene; focus: MarkFocus; label: string }) {
  const [opened, setOpened] = useState<string | null>(null);
  const [surface, setSurface] = useState<PanelSurface>("popover");
  const [rover, setRover] = useState<string | null>(null);
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  const anchorRef = useRef<HTMLButtonElement | null>(null);
  const keys = marks.map((mark) => mark.key);
  const tabStop = rover !== null && keys.includes(rover) ? rover : (keys[0] ?? null);
  const open = marks.find((mark) => mark.key === opened) ?? null;
  const shown = opened === null ? (marks.find((mark) => mark.key === focus.active) ?? null) : null;

  const press = (mark: MapMark, button: HTMLButtonElement) => {
    if (opened === mark.key) {
      setOpened(null);
      return;
    }
    anchorRef.current = button;
    setSurface(panelSurface(window.innerWidth));
    setOpened(mark.key);
    focus.onActive(mark.key);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, mark: MapMark) => {
    if (event.key === "Escape" && opened === null && focus.active !== null) {
      event.preventDefault();
      focus.onActive(null);
      return;
    }
    const next = steppedKey(keys, mark.key, event.key);
    if (next === null) return;
    event.preventDefault();
    buttons.current.get(next)?.focus();
  };

  return (
    <div className="pointer-events-none absolute inset-0" role="group" aria-label={label} data-testid="map-marks">
      {marks.map((mark) => (
        <button
          key={mark.key}
          ref={(node) => {
            if (node) buttons.current.set(mark.key, node);
            else buttons.current.delete(mark.key);
          }}
          type="button"
          tabIndex={mark.key === tabStop ? 0 : -1}
          aria-label={markLabel(mark)}
          aria-haspopup="dialog"
          aria-expanded={opened === mark.key}
          style={markBox(mark, scene.frame)}
          className={BUTTON}
          data-testid="map-mark"
          onClick={(event) => press(mark, event.currentTarget)}
          onKeyDown={(event) => onKeyDown(event, mark)}
          onFocus={() => {
            setRover(mark.key);
            focus.onActive(mark.key);
          }}
          onBlur={() => {
            if (opened !== mark.key) focus.onActive(null);
          }}
          onPointerEnter={() => focus.onActive(mark.key)}
          onPointerLeave={() => {
            if (opened !== mark.key) focus.onActive(null);
          }}
        />
      ))}
      {shown ? <MarkCard mark={shown} scene={scene} /> : null}
      <MarkPanel
        mark={open}
        surface={surface}
        anchorRef={anchorRef}
        onClose={() => {
          setOpened(null);
          focus.onActive(null);
        }}
      />
    </div>
  );
}
