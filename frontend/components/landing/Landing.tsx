"use client";

import { useCiteMaps } from "@/components/landing/CitedText";
import { ClothRibbon } from "@/components/landing/ClothRibbon";
import { InstitutionFooter } from "@/components/landing/Footer";
import { FourChemistries } from "@/components/landing/FourChemistries";
import { HowToRead } from "@/components/landing/HowToRead";
import { LandingHero } from "@/components/landing/LandingHero";
import type { LandingContent } from "@/components/landing/landingContent";
import { CraftsMapSection } from "@/components/map/CraftsMapSection";
import { Appbar } from "@/components/nav/Appbar";
import { SkipLink } from "@/components/shell/ShellFrame";

export function atlasLine(craftCount: number | null): string | null {
  if (craftCount === null) return null;
  return `An atlas of ${craftCount} ${craftCount === 1 ? "craft" : "crafts"}`;
}

export function Landing({ craftCount, content }: { craftCount: number | null; content: LandingContent }) {
  const cite = useCiteMaps(content.sources, content.botanical);
  const atlas = atlasLine(craftCount);
  return (
    <div className="kv-shell">
      <SkipLink />
      <Appbar brandHref="/" tone="photo" overlay>
        {atlas ? <p className="kv-bar-meta tabular-nums">{atlas}</p> : null}
      </Appbar>
      <main id="main-content" tabIndex={-1} className="flex-1">
        <LandingHero craftCount={craftCount} content={content} cite={cite} />
        <ClothRibbon stages={content.stages} name={content.name} craftPath={content.craftPath} />
        <FourChemistries content={content} cite={cite} />
        <HowToRead demo={content.demo} cite={cite} />
        <CraftsMapSection />
      </main>
      <InstitutionFooter />
    </div>
  );
}
