import type { ReactNode } from "react";

import { NameStack, type NameElement, type NameSize } from "@/components/editorial/NameStack";
import { mastheadNameSize, type NativeName } from "@/lib/editorialText";
import { cn } from "@/lib/utils";

export type SpecimenVariant = "landing" | "masthead" | "chapter";

export type SpecimenLabelProps = {
  variant: SpecimenVariant;
  kicker: string;
  family?: string;
  name: string;
  nativeName?: NativeName | null;
  sentence?: ReactNode;
  gi?: ReactNode;
  place?: ReactNode;
  provenance?: ReactNode;
  credit?: ReactNode;
  steps?: ReactNode;
  onPhoto?: boolean;
  headingLevel?: NameElement;
  nameId?: string;
  className?: string;
};

const DEFAULT_ELEMENT: Record<SpecimenVariant, NameElement> = { landing: "p", masthead: "h1", chapter: "h2" };

function nameSize(variant: SpecimenVariant, name: string): NameSize {
  if (variant === "landing") return "h3";
  if (variant === "chapter") return "h2";
  return mastheadNameSize(name);
}

export function SealGlyph() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden focusable="false" className="h-[0.9375rem] w-[0.9375rem] shrink-0">
      <path fill="none" stroke="currentColor" strokeWidth="1.8" d="M16 1.58 L20.23 5.8 L26.2 5.8 L26.2 11.77 L30.42 16 L26.2 20.23 L26.2 26.2 L20.23 26.2 L16 30.42 L11.77 26.2 L5.8 26.2 L5.8 20.23 L1.58 16 L5.8 11.77 L5.8 5.8 L11.77 5.8 Z" />
      <circle cx="16" cy="16" r="4" fill="currentColor" />
    </svg>
  );
}

export function SpecimenLabel({ variant, kicker, family, name, nativeName, sentence, gi, place, provenance, credit, steps, onPhoto = false, headingLevel, nameId, className }: SpecimenLabelProps) {
  const meta = [gi, place].filter(Boolean);
  const Frame = variant === "masthead" ? "div" : "aside";
  return (
    <Frame aria-label={variant === "masthead" ? undefined : "Specimen label"} className={cn("kv-label", className)} data-on-photo={onPhoto ? "" : undefined} data-variant={variant} data-testid="specimen-label">
      <p className="kv-label-kicker kicker">
        <span>{kicker}</span>
        {family ? <span>{family}</span> : null}
      </p>
      <NameStack englishName={name} nativeName={nativeName} size={nameSize(variant, name)} as={headingLevel ?? DEFAULT_ELEMENT[variant]} id={nameId} className="mt-2" />
      {sentence ? <p className="mt-2.5 font-reading text-body-sm leading-normal text-ink-1">{sentence}</p> : null}
      {steps ? <div className="mt-3">{steps}</div> : null}
      {meta.length > 0 ? (
        <div className="kv-label-meta">
          {gi ? (
            <span className="inline-flex items-center gap-1.5">
              <SealGlyph />
              <span>{gi}</span>
            </span>
          ) : null}
          {place ? <span>{place}</span> : null}
        </div>
      ) : null}
      {provenance ? <div className="kv-label-prov">{provenance}</div> : null}
      {credit ? <p className="mt-2 font-ui text-caption text-ink-3 [&_a]:underline-offset-2">{credit}</p> : null}
    </Frame>
  );
}
