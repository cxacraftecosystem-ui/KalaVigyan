"use client";

import { useState, type ReactNode } from "react";
import { Download } from "lucide-react";

import { ListedSources } from "@/components/answer/CitedReading";
import { FormAlert } from "@/components/auth/FormAlert";
import { FactGrid, type Fact } from "@/components/editorial/FactGrid";
import { CitationMenu } from "@/components/learn/ExplainerExport";
import { SlidePreview } from "@/components/learn/SlidePreview";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { TextLink } from "@/components/ui/TextLink";
import { apiErrorMessage } from "@/lib/api";
import { sourceByline, sourceHref, sourceReliabilityLabel } from "@/lib/citations";
import { languageName } from "@/lib/craftRecord";
import { countNoun, formatDate } from "@/lib/format";
import { downloadLessonFile, FILE_FAILED } from "@/lib/lessonApi";
import type { LessonFormat, LessonPack, ReadingItem } from "@/lib/lessonContract";
import { LESSON_FORMAT_LABEL, LESSON_FORMAT_ORDER, slideCountText } from "@/lib/lessonView";

function LessonFiles({ pack }: { pack: LessonPack }) {
  const [busy, setBusy] = useState<LessonFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function fetchFile(format: LessonFormat) {
    setBusy(format);
    setError(null);
    try {
      await downloadLessonFile(pack.id, format);
    } catch (cause) {
      setError(apiErrorMessage(cause, FILE_FAILED));
    } finally {
      setBusy(null);
    }
  }
  return (
    <div className="grid min-w-0 gap-3" data-testid="lesson-files">
      <ActionGroup align="start">
        {LESSON_FORMAT_ORDER.map((format) => (
          <Button key={format} type="button" variant={format === "pptx" ? "primary" : "quiet"} disabled={busy !== null && busy !== format} busy={busy === format} busyLabel="Preparing" onClick={() => void fetchFile(format)} data-format={format}>
            <Download aria-hidden />
            {LESSON_FORMAT_LABEL[format]}
          </Button>
        ))}
      </ActionGroup>
      {error ? <FormAlert>{error}</FormAlert> : null}
    </div>
  );
}

function ReadingEntry({ item }: { item: ReadingItem }) {
  const href = sourceHref(item.source);
  const reliability = item.source.reliability ? sourceReliabilityLabel(item.source.reliability) : null;
  return (
    <li className="grid min-w-0 gap-1 border-b border-rule py-3" data-testid="reading-item">
      <p className="min-w-0 font-reading text-body-sm text-ink-1 [overflow-wrap:anywhere]">
        {href ? (
          <TextLink href={href} external>
            {item.source.title}
          </TextLink>
        ) : (
          item.source.title
        )}
      </p>
      <p className="font-ui text-label text-ink-3">{sourceByline(item.source)}</p>
      <p className="font-ui text-label text-ink-2 tabular-nums">{[reliability, `Cited ${countNoun(item.citedBy, "time")}`].filter(Boolean).join(" · ")}</p>
    </li>
  );
}

function packFacts(pack: LessonPack): Fact[] {
  const facts: (Fact | null)[] = [
    pack.craft ? { label: "Craft", value: <TextLink href={pack.craft.path}>{pack.craft.name}</TextLink> } : null,
    { label: "Slides", value: slideCountText(pack.slides.length) },
    pack.quiz ? { label: "Quiz", value: countNoun(pack.quiz.questions.length, "question") } : null,
    { label: "Reading list", value: countNoun(pack.readingList.length, "reading") },
    { label: "Sources", value: countNoun(pack.sources.length, "source") },
    { label: "Answer version", value: `Version ${pack.version}` },
    { label: "Language", value: languageName(pack.language) },
    { label: "Made", value: formatDate(pack.createdAt) }
  ];
  return facts.filter((fact): fact is Fact => fact !== null);
}

function Part({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="grid min-w-0 gap-4">
      <h2 id={id} className="border-t border-ink-1 pt-4 font-reading text-h3 text-ink-1">
        {title}
      </h2>
      {children}
    </section>
  );
}

export function LessonPackView({ pack }: { pack: LessonPack }) {
  const ref = { explainerId: pack.explainerId, version: pack.version };
  return (
    <div className="grid min-w-0 gap-10" data-testid="lesson-pack">
      <section aria-label="This lesson" className="grid min-w-0 gap-5">
        <FactGrid facts={packFacts(pack)} />
        <LessonFiles pack={pack} />
        <CitationMenu explainer={ref} />
      </section>
      <Part id="slides-heading" title="Slides">
        <SlidePreview pack={pack} />
      </Part>
      <Part id="reading-heading" title="Reading list">
        <ol className="grid min-w-0 border-t border-rule md:grid-cols-2 md:gap-x-8">
          {pack.readingList.map((item) => (
            <ReadingEntry key={item.source.id} item={item} />
          ))}
        </ol>
      </Part>
      <ListedSources sources={pack.sources} idPrefix="lesson-source" />
    </div>
  );
}
