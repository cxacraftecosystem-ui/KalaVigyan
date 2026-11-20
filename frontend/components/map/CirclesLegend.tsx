import { LegendExtras, type LegendExtra } from "@/components/map/ChoroplethLegend";
import { MapPatterns } from "@/components/map/MapBase";
import { circleKeys } from "@/lib/mapStates";
import { cn } from "@/lib/utils";

const KEY_RADIUS = 25.6;
const KEY_X = 27.6;
const KEY_LINE_END = 63.1;
const KEY_TEXT_X = 67.1;
const KEY_PAD = 1.5;
const KEY_TEXT_ROOM = 8;

export function circleKeyBox(): string {
  const bottom = KEY_RADIUS * 2 + KEY_PAD;
  return `0 ${-KEY_TEXT_ROOM} 85 ${bottom + KEY_PAD + KEY_TEXT_ROOM}`;
}

export function CircleKey({ largest }: { largest: number }) {
  const keys = circleKeys(largest);
  const top = keys[keys.length - 1] ?? 1;
  const bottom = KEY_RADIUS * 2 + KEY_PAD;
  return (
    <svg viewBox={circleKeyBox()} className="h-auto w-[85px] shrink-0" aria-hidden data-testid="circle-key">
      {keys.map((value) => {
        const r = KEY_RADIUS * Math.sqrt(value / top);
        const crown = bottom - 2 * r;
        return (
          <g key={value}>
            <circle cx={KEY_X} cy={bottom - r} r={r} fill="none" stroke="var(--ink-2)" strokeWidth={1} />
            <line x1={KEY_X} x2={KEY_LINE_END} y1={crown} y2={crown} stroke="var(--ink-3)" strokeDasharray="2 2" />
            <text x={KEY_TEXT_X} y={crown + 4} className="fill-ink-3 font-ui [font-size:12px] [font-variant-numeric:tabular-nums]">
              {value}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function CirclesLegend({ largest, label, extras, className }: { largest: number; label: string; extras: readonly LegendExtra[]; className?: string }) {
  return (
    <div className={cn("relative flex items-start gap-4 border-t border-rule pt-3 font-ui text-caption text-ink-2", className)} data-testid="map-legend">
      <svg width={0} height={0} aria-hidden className="absolute">
        <MapPatterns />
      </svg>
      {largest > 0 ? <CircleKey largest={largest} /> : null}
      <ul className="grid gap-1.5">
        <li>{label}</li>
        <LegendExtras extras={extras} />
      </ul>
    </div>
  );
}
