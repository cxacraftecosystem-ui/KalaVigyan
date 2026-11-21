"use client";

import { useId } from "react";

import { cropFromTrims, TRIM_MAX, TRIM_SIDES, type Trims } from "@/lib/fieldPhotoReviewView";

export function FieldPhotoCropFields({ trims, width, height, onChange }: { trims: Trims; width: number; height: number; onChange: (next: Trims) => void }) {
  const id = useId();
  const kept = cropFromTrims(trims, width, height);
  return (
    <fieldset className="grid gap-3 border-t border-rule pt-3" aria-describedby={`${id}-kept`}>
      <legend className="field-label">The region to keep</legend>
      <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {TRIM_SIDES.map((side) => (
          <label key={side.key} className="grid gap-1 font-ui text-label text-ink-2">
            <span className="flex items-baseline justify-between gap-3">
              {side.label}
              <span className="text-ink-1 tabular-nums lining-nums">{`${trims[side.key]}%`}</span>
            </span>
            <input
              type="range"
              min={0}
              max={TRIM_MAX}
              step={1}
              value={trims[side.key]}
              aria-valuetext={`${trims[side.key]} per cent`}
              onChange={(event) => onChange({ ...trims, [side.key]: Number(event.currentTarget.value) })}
              className="h-9 w-full min-w-0 cursor-pointer accent-indigo"
            />
          </label>
        ))}
      </div>
      <p id={`${id}-kept`} className="font-ui text-label text-ink-2 tabular-nums lining-nums">
        {`Keeps ${kept.width.toLocaleString("en-IN")} × ${kept.height.toLocaleString("en-IN")} px of ${width.toLocaleString("en-IN")} × ${height.toLocaleString("en-IN")}. Pages show this copy; the original stays private.`}
      </p>
    </fieldset>
  );
}
