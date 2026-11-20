"use client";

import type { ReactNode } from "react";

import { SpecimenLabel } from "@/components/editorial/SpecimenLabel";
import { InstitutionFooter } from "@/components/landing/Footer";
import { HERO_SPECIMEN, HeroCredit, HeroPhoto } from "@/components/landing/heroPicture";
import { Appbar } from "@/components/nav/Appbar";
import { SkipLink } from "@/components/shell/ShellFrame";

function AuthPhoto() {
  return (
    <div className="kv-auth-photo">
      <HeroPhoto priority />
      <div className="kv-hero-scrim" aria-hidden />
      <Appbar brandHref="/" tone="photo" />
      <div className="kv-auth-label">
        <SpecimenLabel variant="landing" onPhoto kicker={HERO_SPECIMEN.kicker} family={HERO_SPECIMEN.family} name={HERO_SPECIMEN.name} credit={<HeroCredit />} />
      </div>
      <p className="kv-auth-credit kv-shell-wrap" data-testid="auth-photo-credit">
        <span className="font-reading text-figcaption italic">{`${HERO_SPECIMEN.name}. `}</span>
        <HeroCredit />
      </p>
    </div>
  );
}

export function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <div className="kv-auth">
      <SkipLink />
      <AuthPhoto />
      <div className="kv-auth-main">
        <div className="kv-shell-wrap flex flex-1 flex-col">
          <main id="main-content" tabIndex={-1} className="kv-auth-body">
            {children}
          </main>
        </div>
        <InstitutionFooter />
      </div>
    </div>
  );
}

export function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children?: ReactNode }) {
  return (
    <AuthFrame>
      <h1 className="m-0 font-headline text-h2 text-ink-1">{title}</h1>
      <p className="mt-2 font-reading text-lede text-ink-2">{subtitle}</p>
      <div className="mt-8">{children}</div>
    </AuthFrame>
  );
}

export function OrDivider() {
  return (
    <div className="my-5 flex items-center gap-3">
      <span className="h-px flex-1 bg-rule" aria-hidden />
      <span className="font-ui text-label text-ink-3">or</span>
      <span className="h-px flex-1 bg-rule" aria-hidden />
    </div>
  );
}
