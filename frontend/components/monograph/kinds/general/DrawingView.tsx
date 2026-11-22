"use client";

import { useId, useMemo } from "react";

import { GeneralFigure } from "@/components/monograph/kinds/general/GeneralFigure";
import { tokenValue, useThemeKey } from "@/components/monograph/kinds/general/useThemeKey";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { drawingRoles, drawingSource, drawingSpecShape, drawingViewBox, parsedSpec, resolvedDrawing, THEME_VARIANTS, type DrawingThemes, type ViewBox } from "@/lib/componentSpecsGeneral";

import "./general.css";
import "./themes.css";

function DrawingImage({ source, box, variant }: { source: string; box: ViewBox; variant?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- a contributed SVG is drawn as an image so it can run no script, which next/image would not load from a data URI
    <img src={drawingSource(source)} width={box.width} height={box.height} alt="" className={variant ? "kv-themed h-auto w-full" : "block h-auto w-full"} data-theme-variant={variant} data-testid="general-drawing" />
  );
}

function ThemedDrawing({ themes, box }: { themes: DrawingThemes; box: ViewBox }) {
  return THEME_VARIANTS.map((variant) => <DrawingImage key={variant} source={themes[variant]} box={box} variant={variant} />);
}

function RoleDrawing({ svg, box }: { svg: string; box: ViewBox }) {
  const theme = useThemeKey();
  const source = useMemo(() => (theme === null ? null : resolvedDrawing(svg, tokenValue)), [svg, theme]);
  if (source === null) return <div className="w-full bg-sunk" style={{ aspectRatio: `${box.width} / ${box.height}` }} aria-hidden="true" />;
  return <DrawingImage source={source} box={box} />;
}

function FixedDrawing({ svg, box }: { svg: string; box: ViewBox }) {
  return (
    <div className="rounded-plate border border-ink-2 bg-raised p-0.5">
      <div className="kv-general-sheet rounded-plate">
        <DrawingImage source={svg} box={box} />
      </div>
    </div>
  );
}

export function DrawingView({ spec, renderUnit }: ComponentViewProps) {
  const drawing = useMemo(() => parsedSpec(drawingSpecShape, spec), [spec]);
  const titleId = useId();
  const altId = useId();
  const box = drawing ? drawingViewBox(drawing.svg) : null;
  if (!drawing || !box) return null;
  const roles = drawingRoles(drawing.svg);
  return (
    <GeneralFigure kind="drawing" head={drawing.head} titleId={titleId} renderUnit={renderUnit}>
      <div className="grid gap-2 lg:grid-cols-[minmax(0,42rem)_minmax(0,20rem)] lg:items-end lg:gap-x-8">
        <div className="w-full min-w-0 [forced-color-adjust:none]" role="img" aria-labelledby={titleId} aria-describedby={altId} data-drawing={drawing.themes ? "themed" : roles ? "roles" : "fixed"}>
          {drawing.themes ? <ThemedDrawing themes={drawing.themes} box={box} /> : roles ? <RoleDrawing svg={drawing.svg} box={box} /> : <FixedDrawing svg={drawing.svg} box={box} />}
        </div>
        <p id={altId} className="max-w-measure border-t border-rule pt-2 font-ui text-label text-ink-2 lg:border-t-0 lg:border-s lg:ps-4 lg:pt-0">
          {renderUnit(drawing.alt)}
        </p>
      </div>
    </GeneralFigure>
  );
}
