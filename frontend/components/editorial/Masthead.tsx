import type { CSSProperties, ReactNode } from "react";

import { PlatePicture } from "@/components/editorial/Plate";
import { SpecimenLabel, type SpecimenLabelProps } from "@/components/editorial/SpecimenLabel";
import { TypographicPlate, type PlateMaterial } from "@/components/editorial/TypographicPlate";
import { focalPosition, focalViewBox, type FocalBox } from "@/lib/commonsPicture";
import { pictureSources } from "@/lib/pictureSources";

export type MastheadPicture = {
  src: string;
  alt: string;
  caption: ReactNode;
  credit: ReactNode;
  wide?: FocalBox;
  narrow?: FocalBox;
  originalWidth?: number;
  originalHeight?: number;
};

export type MastheadProps = {
  label: Omit<SpecimenLabelProps, "variant" | "onPhoto">;
  picture?: MastheadPicture | null;
  material: PlateMaterial;
  plateKicker?: string | null;
};

function focalVariables(picture: MastheadPicture): CSSProperties {
  const variables: Record<string, string> = {};
  if (picture.narrow) Object.assign(variables, { "--focal-narrow-at": focalPosition(picture.narrow), "--focal-narrow-box": focalViewBox(picture.narrow) });
  if (picture.wide) Object.assign(variables, { "--focal-wide-at": focalPosition(picture.wide), "--focal-wide-box": focalViewBox(picture.wide) });
  return variables as CSSProperties;
}

function pictureSize({ originalWidth, originalHeight }: MastheadPicture): { width: number; height: number } | undefined {
  return originalWidth && originalHeight ? { width: originalWidth, height: originalHeight } : undefined;
}

function MastheadFigure({ picture }: { picture: MastheadPicture }) {
  return (
    <figure className="kv-masthead-figure">
      <PlatePicture alt={picture.alt} sources={pictureSources(picture.src, "masthead", picture.originalWidth)} size={pictureSize(picture)} priority className="kv-masthead-picture" />
      <figcaption className="kv-masthead-caption">
        <p className="kv-caption">{picture.caption}</p>
        <p className="kv-credit">{picture.credit}</p>
      </figcaption>
    </figure>
  );
}

export function Masthead({ label, picture, material, plateKicker }: MastheadProps) {
  return (
    <header data-testid="masthead">
      <div className="kv-masthead" data-photo={picture ? "" : undefined} style={picture ? focalVariables(picture) : undefined}>
        {picture ? (
          <MastheadFigure picture={picture} />
        ) : (
          <TypographicPlate material={material} englishName={label.name} nativeName={label.nativeName} kicker={plateKicker} size="masthead" decorative className="kv-masthead-picture" />
        )}
        <SpecimenLabel {...label} variant="masthead" />
      </div>
    </header>
  );
}
