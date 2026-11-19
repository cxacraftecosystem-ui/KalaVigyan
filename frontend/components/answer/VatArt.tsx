"use client";

import { useId, type Ref } from "react";

import type { VatFrame } from "@/lib/answerVat";

const VAT_RIM = "M44 150 L196 150 L162 248 Q120 262 78 248 Z";
const VAT_LIQUOR = "M53 160 L187 160 L157 243 Q120 255 83 243 Z";
const CLOTH_DOWN = "M100 162 L140 162 L141 236 L99 236 Z";
const CLOTH_UP = "M100 20 L140 20 L141 132 L99 132 Z";
const DRIPS = ["M108 138 q2 5 0 7 q-2 -2 0 -7z", "M122 141 q2 5 0 7 q-2 -2 0 -7z", "M133 137 q2 5 0 7 q-2 -2 0 -7z"];

export type VatArtRefs = { dipRef: Ref<SVGGElement>; airRef: Ref<SVGGElement> };

function svgId(raw: string): string {
  return raw.replace(/[^a-zA-Z0-9_-]/g, "");
}

function Ground({ strata }: { strata: string }) {
  return (
    <>
      <rect x="0" y="150" width="240" height="120" fill="var(--sunk)" />
      <rect x="0" y="150" width="240" height="120" fill={`url(#${strata})`} />
      <path d={VAT_RIM} fill="var(--raised)" stroke="var(--ink-1)" strokeWidth="1.4" />
      <path d={VAT_LIQUOR} fill="var(--dye-vat-liquor)" />
      <rect x="0" y="150" width="240" height="2" fill="var(--ink-1)" />
      <line x1="60" y1="20" x2="200" y2="20" stroke="var(--ink-1)" strokeWidth="2.2" strokeLinecap="round" />
    </>
  );
}

function Cloth({ d, fill, weave, opacity }: { d: string; fill: string; weave: string; opacity?: number }) {
  return (
    <>
      <path d={d} fill={fill} opacity={opacity} />
      <path d={d} fill={`url(#${weave})`} />
      <path d={d} fill="none" stroke="var(--ink-1)" strokeWidth="1" />
    </>
  );
}

function Oxygen() {
  return (
    <g className="max-md:hidden">
      <g stroke="var(--ink-3)" strokeWidth="1" fill="none">
        <path d="M196 46 L150 52" />
        <path d="M196 82 L150 84" />
      </g>
      <path d="M146 50 l6 2 l-5 4 z M146 82 l6 2 l-6 3 z" fill="var(--ink-3)" />
      <g fill="var(--ink-2)" fontFamily="var(--font-reading)" fontSize="18">
        <text x="196" y="52">
          O<tspan fontSize="14" dy="4">2</tspan>
        </text>
        <text x="196" y="88">
          O<tspan fontSize="14" dy="4">2</tspan>
        </text>
      </g>
    </g>
  );
}

function FrameArt({ frame, dip, ids, dipRef, airRef }: VatArtRefs & { frame: VatFrame["key"]; dip: number; ids: { strata: string; weave: string } }) {
  if (frame === "in") {
    return (
      <g ref={dipRef} className="motion-dip">
        <Cloth d={CLOTH_DOWN} fill="var(--dye-leuco)" weave={ids.weave} opacity={0.42} />
      </g>
    );
  }
  if (frame === "lifted") {
    return (
      <g>
        <Cloth d={CLOTH_UP} fill="var(--dye-leuco)" weave={ids.weave} />
        <g fill="var(--dye-vat-liquor)" stroke="var(--ink-1)" strokeWidth=".6">
          {DRIPS.map((d) => (
            <path key={d} d={d} />
          ))}
        </g>
      </g>
    );
  }
  return (
    <g>
      <Cloth d={CLOTH_UP} fill={`var(--dip-${dip})`} weave={ids.weave} />
      <g ref={airRef} className="motion-oxidise">
        <Cloth d={CLOTH_UP} fill="var(--dye-leuco)" weave={ids.weave} />
      </g>
      <Oxygen />
    </g>
  );
}

export function VatArt({ frame, dip, dipRef, airRef }: VatArtRefs & { frame: VatFrame["key"]; dip: number }) {
  const base = svgId(useId());
  const ids = { strata: `${base}-strata`, weave: `${base}-weave` };
  return (
    <svg viewBox="0 0 240 270" className="block h-auto w-full" aria-hidden data-frame-art={frame}>
      <defs>
        <pattern id={ids.strata} width="10" height="8" patternUnits="userSpaceOnUse">
          <path d="M0 4 H6" stroke="var(--ink-3)" strokeOpacity=".35" strokeWidth=".8" />
          <path d="M5 0 H10 M-5 0 H0" stroke="var(--ink-3)" strokeOpacity=".2" strokeWidth=".8" />
        </pattern>
        <pattern id={ids.weave} width="3" height="3" patternUnits="userSpaceOnUse">
          <path d="M0 3 L3 0" stroke="black" strokeOpacity=".07" strokeWidth=".6" />
          <path d="M0 0 L3 3" stroke="white" strokeOpacity=".06" strokeWidth=".5" />
        </pattern>
      </defs>
      <Ground strata={ids.strata} />
      <FrameArt frame={frame} dip={dip} ids={ids} dipRef={dipRef} airRef={airRef} />
    </svg>
  );
}
