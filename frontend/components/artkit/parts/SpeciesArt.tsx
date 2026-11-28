import type { SpeciesMark } from "@/lib/artKit";
import { KIT_REACTION_CLASS } from "@/lib/artKitMotion";
import type { SpeciesPart } from "@/lib/componentSpecsKit";

import type { Moving, PartIds } from "../kitIds";
import { INK, INK_SOFT, MaterialPath, PAPER } from "../surfaces";

export const BEAD = "M14 60 A46 46 0 1 0 106 60 A46 46 0 1 0 14 60 Z";
export const GLINT = "M34 44 A30 30 0 0 1 54 28";
export const GAS = "M30 46 A14 14 0 1 0 58 46 A14 14 0 1 0 30 46 Z M64 52 A14 14 0 1 0 92 52 A14 14 0 1 0 64 52 Z M40 82 A14 14 0 1 0 68 82 A14 14 0 1 0 40 82 Z";
export const CORE = "M42 60 A18 18 0 1 0 78 60 A18 18 0 1 0 42 60 Z";
const CRACK = "M60 14 L51 40 L66 58 L52 80 L60 106";
const ARRIVAL = "M60 1 V11 M54 5 L60 11 L66 5";

function Crack({ moving }: { moving?: Moving }) {
  const lines = (
    <>
      <path d={CRACK} fill="none" stroke={PAPER} strokeWidth="5" strokeLinejoin="round" />
      <path d={CRACK} fill="none" stroke={INK} strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round" />
    </>
  );
  if (!moving) return <g data-kit-break="">{lines}</g>;
  return (
    <g data-kit-break="" className={KIT_REACTION_CLASS.break} data-kit-move={moving.panel}>
      {lines}
    </g>
  );
}

function Marked({ mark }: { mark: SpeciesMark }) {
  if (mark === "gas") return <path d={GAS} fill={PAPER} stroke={INK_SOFT} strokeWidth="1.4" />;
  if (mark === "ion") {
    return (
      <>
        <path d={BEAD} fill={PAPER} stroke={INK} strokeWidth="1.6" />
        <path d={CORE} fill="none" stroke={INK_SOFT} strokeWidth="1.4" />
      </>
    );
  }
  return (
    <>
      <path d={BEAD} fill={PAPER} stroke={INK_SOFT} strokeWidth="1.4" />
      <path d={GLINT} fill="none" stroke={INK_SOFT} strokeWidth="3" strokeLinecap="round" />
    </>
  );
}

function Bead({ part, ids }: { part: SpeciesPart; ids: PartIds }) {
  if (part.material) return <MaterialPath d={BEAD} material={part.material} ids={ids} texture="speckle" />;
  if (part.mark) return <Marked mark={part.mark} />;
  return <path d={BEAD} fill={PAPER} stroke={INK_SOFT} strokeWidth="1.4" strokeDasharray="6 4" />;
}

export function SpeciesArt({ part, ids, moving }: { part: SpeciesPart; ids: PartIds; moving?: Moving }) {
  const uncoloured = !part.material && !part.mark;
  return (
    <g data-kit-part="species" data-kit-role={part.role} data-kit-mark={part.material ? undefined : (part.mark ?? undefined)} data-kit-uncoloured={uncoloured ? "" : undefined}>
      <Bead part={part} ids={ids} />
      {part.breaks ? <Crack moving={moving} /> : null}
      {part.role === "reagent" ? <path d={ARRIVAL} fill="none" stroke={INK_SOFT} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /> : null}
    </g>
  );
}
