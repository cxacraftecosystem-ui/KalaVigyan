"use client";

import { useId, useMemo } from "react";

import { GeneralFigure } from "@/components/monograph/kinds/general/GeneralFigure";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { drawingSource, drawingSpecShape, drawingViewBox, parsedSpec } from "@/lib/componentSpecsGeneral";

import "./general.css";

export function DrawingView({ spec, renderUnit }: ComponentViewProps) {
  const drawing = useMemo(() => parsedSpec(drawingSpecShape, spec), [spec]);
  const titleId = useId();
  const altId = useId();
  const box = drawing ? drawingViewBox(drawing.svg) : null;
  if (!drawing || !box) return null;
  return (
    <GeneralFigure kind="general_drawing" head={drawing.head} titleId={titleId} renderUnit={renderUnit}>
      <div className="grid gap-2">
        <div className="rounded-plate border border-ink-2 bg-raised p-0.5" role="img" aria-labelledby={titleId} aria-describedby={altId}>
          <div className="kv-general-sheet rounded-plate">
            {/* eslint-disable-next-line @next/next/no-img-element -- a contributed SVG is drawn as an image so it can run no script, which next/image would not load from a data URI */}
            <img src={drawingSource(drawing.svg)} width={box.width} height={box.height} alt="" className="block h-auto w-full" data-testid="general-drawing" />
          </div>
        </div>
        <p id={altId} className="max-w-measure font-ui text-label text-ink-2">
          {renderUnit(drawing.alt)}
        </p>
      </div>
    </GeneralFigure>
  );
}
