import type { MapScene } from "@/components/map/MapCanvas";
import { CARD_WIDTH_PX, cardPlacement, countLine, firstCrafts, type MapMark } from "@/components/map/markPlacement";

export function MarkCard({ mark, scene }: { mark: MapMark; scene: MapScene }) {
  const { names, rest } = firstCrafts(mark);
  return (
    <div
      aria-hidden="true"
      style={{ ...cardPlacement(mark, scene), width: CARD_WIDTH_PX }}
      className="pointer-events-none absolute z-popover max-w-full rounded-card border border-rule bg-raised px-3 py-2.5 shadow-pop"
      data-testid="map-mark-card"
    >
      <p className="font-ui text-ui font-semibold text-ink-1">{mark.name}</p>
      <p className="mt-0.5 font-ui text-caption text-ink-3 [font-variant-numeric:lining-nums_tabular-nums]">{countLine(mark.count)}</p>
      {names.length ? (
        <p className="mt-1.5 font-reading text-body-sm text-ink-2">
          {names.join(", ")}
          {rest > 0 ? <span className="font-ui text-caption text-ink-3">{` and ${rest.toLocaleString("en-IN")} more`}</span> : null}
        </p>
      ) : null}
    </div>
  );
}
