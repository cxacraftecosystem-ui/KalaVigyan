"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { SpecimenLabel } from "@/components/editorial/SpecimenLabel";
import { CitedText, useCiteMaps } from "@/components/landing/CitedText";
import { HERO_SPECIMEN, HeroCredit, HeroPhoto } from "@/components/landing/heroPicture";
import type { LandingContent } from "@/components/landing/landingContent";
import { VAT_PLAYED_KEY, VatSteps } from "@/components/landing/VatSteps";
import { useVatMoment } from "@/components/motion/useVatMoment";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { buttonLook } from "@/components/ui/button";

export const HERO_TITLE_ID = "landing-title";

export const ATLAS_HREF = "/crafts";
export const ACCESS_LINE = "Reading is open to everyone.";
export const ACCESS_LINK = "Request access to ask questions and contribute";

export function fieldsLine(craftCount: number | null): string {
  const reach = craftCount === null ? "India’s crafts" : `${craftCount.toLocaleString("en-IN")} ${craftCount === 1 ? "craft" : "crafts"}`;
  return `Sixteen fields across ${reach}, from materials and chemistry to ecology, history, design and policy. Every sentence opens to its source’s own words.`;
}

function usePhotoShown(host: React.RefObject<HTMLElement | null>): boolean {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const image = host.current?.querySelector("img");
    if (!image) return;
    if (image.complete) {
      setShown(true);
      return;
    }
    const done = () => setShown(true);
    image.addEventListener("load", done, { once: true });
    return () => image.removeEventListener("load", done);
  }, [host]);
  return shown;
}

function HeroActions() {
  const { user } = useAuth();
  if (user) {
    return (
      <ActionGroup align="start" className="kv-hero-actions">
        <Link href="/ask" {...buttonLook({ variant: "primary", onPhoto: true })}>
          Start asking
        </Link>
        <Link href={ATLAS_HREF} {...buttonLook({ variant: "quiet", onPhoto: true })}>
          Explore the crafts
        </Link>
      </ActionGroup>
    );
  }
  return (
    <>
      <ActionGroup align="start" className="kv-hero-actions">
        <Link href={ATLAS_HREF} {...buttonLook({ variant: "primary", onPhoto: true })}>
          Explore the crafts
        </Link>
        <Link href="/login" {...buttonLook({ variant: "quiet", onPhoto: true })}>
          Sign in
        </Link>
      </ActionGroup>
      <p className="kv-hero-access font-ui text-label">
        {ACCESS_LINE}{" "}
        <Link href="/signup" className="kv-hero-access-link">
          {ACCESS_LINK}
        </Link>
      </p>
    </>
  );
}

function HeroText({ craftCount }: { craftCount: number | null }) {
  return (
    <div className="kv-hero-in kv-on-photo">
      <p className="kicker kv-hero-kicker">Science behind craft</p>
      <h1 id={HERO_TITLE_ID} className="kv-hero-title font-headline text-hero lining-nums">
        The science in India’s crafts, <em>sourced to the sentence.</em>
      </h1>
      <p className="kv-hero-dek font-reading text-lede">{fieldsLine(craftCount)}</p>
      <HeroActions />
    </div>
  );
}

export function LandingHero({ craftCount, content }: { craftCount: number | null; content: LandingContent }) {
  const cite = useCiteMaps(content.sources);
  const host = useRef<HTMLElement | null>(null);
  const shown = usePhotoShown(host);
  const vat = useVatMoment({ autoplayKey: shown ? VAT_PLAYED_KEY : undefined });
  return (
    <section ref={host} className="kv-hero" data-vat-phase={vat.phase} aria-labelledby={HERO_TITLE_ID} data-testid="landing-hero">
      <HeroPhoto priority />
      <div className="vat-tint kv-hero-tint" aria-hidden />
      <div className="kv-hero-scrim" aria-hidden />
      <div className="kv-shell-wrap kv-hero-grid">
        <HeroText craftCount={craftCount} />
        <SpecimenLabel
          variant="landing"
          onPhoto
          kicker={HERO_SPECIMEN.kicker}
          family={content.family ?? undefined}
          name={content.name}
          nameId="landing-specimen"
          sentence={content.vat ? <CitedText sentence={content.vat} cite={cite} /> : undefined}
          steps={<VatSteps phase={vat.phase} onPlay={vat.play} />}
          gi={content.gi ? <CitedText sentence={content.gi} cite={cite} /> : undefined}
          place={content.place ?? undefined}
          credit={<HeroCredit />}
          className="kv-hero-label"
        />
      </div>
    </section>
  );
}
