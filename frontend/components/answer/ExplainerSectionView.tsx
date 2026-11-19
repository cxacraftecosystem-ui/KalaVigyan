"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";

import { useCitations } from "@/components/answer/CitationContext";
import { ExplainerBlockView } from "@/components/answer/ExplainerBlockView";
import { useExplainerReading } from "@/components/answer/ExplainerReading";
import { ExpertPanel } from "@/components/answer/experts/ExpertPanel";
import { MediaPlate } from "@/components/answer/MediaPlate";
import { MarginNotes, Spread } from "@/components/editorial/MarginNotes";
import { marginPicture, scriptLeading, sectionNotes, textScript } from "@/lib/answerEssay";
import { headingView } from "@/lib/answerLanguages";
import type { SectionView } from "@/lib/explainerState";
import { DISCIPLINE_LABEL, sectionAnchor, workingLabel } from "@/lib/explainerView";
import { sectionRuns } from "@/lib/expertPanel";
import { cn } from "@/lib/utils";

export const SECTION_VIEWPORT = { margin: "-45% 0px -45% 0px", amount: "some" } as const;

function WorkingState({ label }: { label: string }) {
  return (
    <p role="status" className="mt-3 inline-flex items-center gap-2 font-ui text-label text-ink-3" data-testid="section-working">
      <span className="kv-spin" aria-hidden />
      {label}
    </p>
  );
}

function SectionMargin({ section }: { section: SectionView }) {
  const { numbers, sourcesById } = useCitations();
  const notes = useMemo(() => sectionNotes(section.blocks, numbers, sourcesById), [section.blocks, numbers, sourcesById]);
  const picture = marginPicture(section.blocks);
  if (notes.length === 0 && !picture) return null;
  return (
    <>
      {notes.length > 0 ? <MarginNotes notes={notes} label="Sources in this section" /> : null}
      {picture ? <MediaPlate media={picture.media} role="margin" className="mt-6 [&_.kv-caption]:text-ui" /> : null}
    </>
  );
}

function SectionRail({ number, label }: { number: number; label: string }) {
  return (
    <div className="grid gap-2">
      <span className="block font-headline text-numeral font-light text-ink-3 lining-nums">{number}</span>
      <span className="font-ui text-label text-ink-3">{label}</span>
    </div>
  );
}

export function ExplainerSectionView({ section, streaming, reduce, onActive, number = 1 }: { section: SectionView; streaming: boolean; reduce: boolean; onActive: (id: string) => void; number?: number }) {
  const { language, original } = useExplainerReading();
  const heading = headingView({ id: section.id, heading: section.title, original: section.original, sentences: [] }, language, original);
  const script = textScript(heading.lang, language);
  const anchor = sectionAnchor(section.id);
  const working = workingLabel(section.state, streaming);
  const discipline = DISCIPLINE_LABEL[section.discipline];
  const marginBlock = marginPicture(section.blocks)?.blockId ?? null;

  return (
    <motion.section id={anchor} aria-labelledby={`${anchor}-title`} viewport={SECTION_VIEWPORT} onViewportEnter={() => onActive(section.id)} className="kv-chapter min-w-0 py-12 rail:py-16" data-testid="explainer-section" data-state={section.state}>
      <Spread rail={<SectionRail number={number} label={discipline} />} margin={<SectionMargin section={section} />}>
        <p className="kicker mb-4 flex items-center gap-3 after:h-px after:w-10 after:flex-none after:bg-ink-3 rail:hidden">
          {number} · {discipline}
        </p>
        <h2 id={`${anchor}-title`} lang={heading.lang} dir={heading.dir} data-script={script ?? undefined} className={cn("font-headline text-h2 text-ink-1", scriptLeading(script, "display"))}>
          {heading.text}
        </h2>
        {working ? <WorkingState label={working} /> : null}
        {section.blocks.length > 0 ? (
          <div className="mt-5 grid min-w-0 grid-cols-[minmax(0,1fr)] gap-6">
            {sectionRuns(section.blocks).map((run) =>
              run.kind === "experts" ? (
                <ExpertPanel key={run.key} views={run.views} reduce={reduce} />
              ) : (
                <div key={run.block.id} className={run.block.id === marginBlock ? "min-w-0 rail:hidden" : "min-w-0"}>
                  <ExplainerBlockView block={run.block} reduce={reduce} />
                </div>
              )
            )}
          </div>
        ) : null}
      </Spread>
    </motion.section>
  );
}
