"use client";

import type { ReactNode } from "react";
import { Clapperboard, Play, RefreshCw } from "lucide-react";

import { UnderstoodLine, type UnderstoodChange } from "@/components/answer/UnderstoodLine";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { ENGLISH, type AnswerLanguage } from "@/lib/answerLanguages";
import type { Understood } from "@/lib/explainerContract";

export const ORIGINAL_TEXT = "original";
export const TRANSLATED_TEXT = "translated";

export type ShownText = { translated: boolean; original: boolean; onShow: (value: string) => void };

export type ReadingTools = { onListen: (() => void) | null; onFresh: (() => void) | null; onFilm?: (() => void) | null; tools?: ReactNode };

function ToolButtons({ onListen, onFresh, onFilm = null, tools = null }: ReadingTools) {
  return (
    <ActionGroup align="end" data-testid="reading-tools">
      {onListen ? (
        <Button variant="quiet" size="sm" onClick={onListen} data-testid="listen-start">
          <Play className="h-4 w-4" aria-hidden />
          Listen
        </Button>
      ) : null}
      {onFilm ? (
        <Button variant="quiet" size="sm" onClick={onFilm} data-testid="film-start">
          <Clapperboard className="h-4 w-4" aria-hidden />
          Film
        </Button>
      ) : null}
      {onFresh ? (
        <Button variant="quiet" size="sm" onClick={onFresh} data-testid="fresh-research">
          <RefreshCw className="h-4 w-4" aria-hidden />
          Research again
        </Button>
      ) : null}
      {tools}
    </ActionGroup>
  );
}

export function hasReadingTools(reading: ReadingTools): boolean {
  return Boolean(reading.onListen || reading.onFresh || reading.onFilm || reading.tools);
}

export function ReadingToolsBand(reading: ReadingTools) {
  if (!hasReadingTools(reading)) return null;
  return (
    <section aria-labelledby="reading-tools-heading" className="mx-auto mt-12 grid w-full max-w-measure gap-3 border-t border-rule pt-4" data-testid="reading-tools-band">
      <h2 id="reading-tools-heading" className="kicker">
        Use this answer
      </h2>
      <ToolButtons {...reading} />
    </section>
  );
}

export function ExplainerHeader({
  understood,
  depthLabel,
  language,
  change,
  shown,
  ...reading
}: ReadingTools & {
  understood: Understood | null;
  depthLabel: string | null;
  language: AnswerLanguage;
  change: UnderstoodChange;
  shown: ShownText;
}) {
  if (!understood && !shown.translated && !hasReadingTools(reading)) return null;
  return (
    <div className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-3 border-b border-rule pb-3" data-testid="answer-toolbar">
      {understood ? <UnderstoodLine understood={understood} depthLabel={depthLabel} language={language} change={change} /> : <span />}
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        {shown.translated ? (
          <SegmentedChoice
            label="Answer text"
            value={shown.original ? ORIGINAL_TEXT : TRANSLATED_TEXT}
            options={[
              { value: TRANSLATED_TEXT, label: language.autonym },
              { value: ORIGINAL_TEXT, label: ENGLISH.label }
            ]}
            onChange={shown.onShow}
          />
        ) : null}
        {hasReadingTools(reading) ? <ToolButtons {...reading} /> : null}
      </div>
    </div>
  );
}
