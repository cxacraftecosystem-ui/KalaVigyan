import { useId, type ReactNode } from "react";

import { PLATE_TEXTURES, type PlateTexture, type TextureName } from "@/components/editorial/plateTextures";
import { shownNativeName, type NativeName } from "@/lib/editorialText";
import { cn } from "@/lib/utils";

export type PlateMaterial = "textile" | "metal" | "wood" | "fibre" | "clay" | "stone" | "paper" | "leather" | "paint" | "instr" | "toys" | "misc";

export const MATERIAL_TEXTURE: Record<PlateMaterial, TextureName> = {
  textile: "twill",
  metal: "hammer",
  wood: "grain",
  fibre: "weave",
  clay: "plaster",
  stone: "speckle",
  paper: "laid",
  leather: "pebble",
  paint: "brush",
  instr: "grain",
  toys: "plaster",
  misc: "brush"
};

const LONG_NAME = 14;

export function PlateGround({ material }: { material: PlateMaterial }) {
  const id = `plate-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const texture: PlateTexture = PLATE_TEXTURES[MATERIAL_TEXTURE[material]];
  return (
    <svg className="kv-plate-ground" aria-hidden focusable="false">
      <defs>
        <pattern id={id} width={texture.width} height={texture.height} patternUnits="userSpaceOnUse">
          {texture.marks.map((mark) => (
            <path key={mark.d.slice(0, 24)} d={mark.d} fill={mark.fill ? "var(--gm)" : "none"} stroke={mark.fill ? "none" : "var(--gm)"} strokeWidth={mark.stroke} strokeLinecap={mark.round ? "round" : undefined} />
          ))}
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${id})`} />
    </svg>
  );
}

export type PlateSize = "card" | "masthead" | "small";

export type TypographicPlateProps = {
  material: PlateMaterial;
  englishName: string;
  nativeName?: NativeName | null;
  kicker?: string | null;
  size?: PlateSize;
  strip?: ReactNode;
  decorative?: boolean;
  className?: string;
};

const PLATE_HEIGHT: Record<PlateSize, string> = { card: "min-h-44", small: "min-h-24", masthead: "min-h-0" };

const PLATE_BODY: Record<PlateSize, string> = {
  card: "items-start px-4 pt-3.5 pb-4",
  small: "items-start p-2.5",
  masthead: "items-end px-6 py-[22px] text-end lg:px-11 lg:py-[34px]"
};

const NAME_BOX: Record<PlateSize, string> = {
  card: "mt-auto pt-5",
  small: "mt-auto pt-5",
  masthead: "order-first lg:max-w-[52%]"
};

export function TypographicPlate({ material, englishName, nativeName, kicker, size = "card", strip, decorative = false, className }: TypographicPlateProps) {
  const shown = shownNativeName(nativeName);
  const name = shown?.text ?? englishName;
  return (
    <div className={cn("kv-plate", `g-${material}`, PLATE_HEIGHT[size], className)} data-size={size} data-material={material} aria-hidden={decorative || undefined} data-testid="typographic-plate">
      <PlateGround material={material} />
      <div className={cn("flex flex-1 flex-col", PLATE_BODY[size])}>
        {kicker && size !== "small" ? <span className={cn("kv-knock kicker m-0.5 text-inherit", size === "masthead" && "mt-auto")}>{kicker}</span> : null}
        <span className={cn("max-w-full min-w-0", NAME_BOX[size])}>
          {shown ? (
            <span lang={shown.lang} data-script={shown.script} dir={shown.dir} className="kv-plate-name kv-knock" data-long={name.length > LONG_NAME ? "" : undefined}>
              {name}
            </span>
          ) : (
            <span className="kv-plate-name kv-knock" data-latin="">
              {name}
            </span>
          )}
        </span>
      </div>
      {strip ? <div className="grid gap-[3px] border-t border-rule bg-raised px-3 pt-2 pb-2.5 font-ui text-ink-1">{strip}</div> : null}
    </div>
  );
}
