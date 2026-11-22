import type { Metadata } from "next";

import { VoiceDockBoard } from "@/app/design/voice/VoiceDockBoard";
import { BrandLockup } from "@/components/BrandMark";

export const metadata: Metadata = {
  title: "Voice dock",
  description: "The live call's dock drawn by the components a call uses, for the release check of its states.",
  robots: { index: false, follow: false }
};

export default function VoiceDockPage() {
  return (
    <div className="min-h-dvh bg-ground text-ink-1">
      <header className="border-b border-ink-1">
        <div className="mx-auto grid max-w-content gap-6 px-4 pt-7 pb-6 sm:px-6 md:px-10 rail:px-12 xl:px-16">
          <BrandLockup />
          <h1 className="max-w-[16ch] font-headline text-h1">The voice dock</h1>
        </div>
      </header>
      <main id="main-content" className="mx-auto max-w-content px-4 sm:px-6 md:px-10 rail:px-12 xl:px-16">
        <VoiceDockBoard />
      </main>
    </div>
  );
}
