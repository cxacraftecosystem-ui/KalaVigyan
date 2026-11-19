"use client";

import { useMemo, useState } from "react";

import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { answerAddress, answerCitationIn, CITATION_STYLES, type AnswerCitation, type CitationStyle } from "@/lib/answerCitation";
import { SHARED_ANSWER_PAGE } from "@/lib/shareContract";
import { cn } from "@/lib/utils";

export type CitedAnswer = Pick<AnswerCitation, "explainerId" | "version" | "question" | "answeredAt" | "sources">;

const COPIED = "Citation copied.";
const NOT_COPIED = "Couldn't copy. Select the citation and copy it.";

function readerPlace(): { origin: string; path: string | null } {
  const { origin, pathname } = window.location;
  return { origin, path: pathname.startsWith(SHARED_ANSWER_PAGE) ? pathname : null };
}

function isStyle(value: string): value is CitationStyle {
  return CITATION_STYLES.some((style) => style.value === value);
}

export function CiteAnswer({ id, answer }: { id: string; answer: CitedAnswer }) {
  const [style, setStyle] = useState<CitationStyle>("text");
  const [copied, setCopied] = useState<string | null>(null);
  const citation = useMemo<AnswerCitation>(() => ({ ...answer, ...readerPlace(), accessedAt: new Date() }), [answer]);
  const text = answerCitationIn(style, citation);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(COPIED);
    } catch {
      setCopied(NOT_COPIED);
    }
  }

  return (
    <section id={id} aria-labelledby={`${id}-title`} className="mt-6 grid justify-items-center gap-3 border-y border-ink-1 px-0 py-6 text-center sm:px-6" data-testid="cite-answer">
      <h2 id={`${id}-title`} className="kicker">
        Cite this answer
      </h2>
      <SegmentedChoice label="Citation style" value={style} options={CITATION_STYLES} onChange={(next) => {
          if (isStyle(next)) setStyle(next);
        }}
      />
      <p
        className={cn(
          "max-w-[62ch] [overflow-wrap:anywhere]",
          style === "bibtex" ? "w-full whitespace-pre-wrap rounded-control bg-sunk px-3.5 py-3 text-start font-code text-label text-ink-1" : "font-reading text-body-sm text-ink-1"
        )}
        data-testid="cite-answer-text"
      >
        {text}
      </p>
      <p className="font-ui text-label text-ink-3 [overflow-wrap:anywhere]">
        Version {answer.version} stays at <span className="font-code text-ink-2">{answerAddress(citation)}</span>
      </p>
      <ActionGroup>
        <Button variant="quiet" size="sm" onClick={() => void copy()}>
          Copy citation
        </Button>
      </ActionGroup>
      <p role="status" className="min-h-[1.4em] font-ui text-label text-ink-3">
        {copied}
      </p>
    </section>
  );
}
