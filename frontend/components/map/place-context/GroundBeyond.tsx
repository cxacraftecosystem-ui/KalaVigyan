import { RotatedLabel } from "@/components/map/physical/RotatedLabel";
import type { DrawnRiver } from "@/components/map/place-context/useGroundRivers";
import { inFrame, linePath, placed, type FrameView } from "@/lib/groundFrame";
import type { GroundFrame, GroundPin } from "@/lib/placeGround";

export const ABROAD_PIN_PX = 5;
export const NAMED_RIVER_PX = 2.25;
const HALO_SHARE = 2.2;
const LABEL_GAP_PX = 6;

function nameAt(river: DrawnRiver, frame: GroundFrame): readonly [number, number] | null {
  const inside = river.lines.flat().filter((point) => inFrame(frame, point));
  return inside.length ? inside[Math.floor(inside.length / 2)] : null;
}

export function NamedRivers({ rivers, frame, view }: { rivers: readonly DrawnRiver[]; frame: GroundFrame; view: FrameView }) {
  if (!rivers.length) return null;
  return (
    <g className="pointer-events-none" fill="none" strokeLinecap="round" strokeLinejoin="round" data-testid="ground-named-rivers">
      {rivers.map((drawn) => {
        const d = drawn.lines.map((line) => linePath(view, line)).join("");
        const at = nameAt(drawn, frame);
        const label = at ? placed(view, at) : null;
        return (
          <g key={drawn.river.key} data-river={drawn.river.mainRiv}>
            <path d={d} stroke="var(--map-label-halo)" strokeWidth={NAMED_RIVER_PX * HALO_SHARE} vectorEffect="non-scaling-stroke" />
            <path d={d} stroke="var(--map-river)" strokeWidth={NAMED_RIVER_PX} vectorEffect="non-scaling-stroke" data-testid="ground-named-river" />
            {label ? (
              <RotatedLabel x={label.x} y={label.y} angle={0} tone="var(--map-water-label)" italic lift>
                {drawn.river.name}
              </RotatedLabel>
            ) : null}
          </g>
        );
      })}
    </g>
  );
}

export function AbroadPins({ pins, view, k }: { pins: readonly GroundPin[]; view: FrameView; k: number }) {
  if (!pins.length) return null;
  return (
    <g className="pointer-events-none" data-testid="ground-abroad">
      {pins.map((pin) => {
        const { x, y } = placed(view, [pin.longitude, pin.latitude]);
        return (
          <g key={pin.key}>
            <circle cx={x} cy={y} r={ABROAD_PIN_PX * k} fill="var(--map-label-halo)" stroke="var(--terracotta)" strokeWidth={2.5} vectorEffect="non-scaling-stroke" data-testid="ground-abroad-pin" />
            <RotatedLabel x={x} y={y} angle={0} anchor="start" dx={(ABROAD_PIN_PX + LABEL_GAP_PX) * k} weight="medium">
              {pin.name}
            </RotatedLabel>
          </g>
        );
      })}
    </g>
  );
}
