"use client";

import type { ReactNode } from "react";

import { DictationControl } from "@/components/ask/DictationControl";
import type { Dictation } from "@/components/ask/useDictation";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import type { AnswerLanguage } from "@/lib/answerLanguages";
import { QUESTION_MAX } from "@/lib/askRequest";

function stopAction(dictation: Dictation, busy: boolean, onStop: () => void): { label: string; act: () => void } | null {
  if (dictation.listening) return { label: "Stop dictation", act: dictation.stop };
  return busy ? { label: "Stop the answer", act: onStop } : null;
}

export function AskBox({
  value,
  onChange,
  onSubmit,
  onStop,
  busy,
  canAsk,
  dictation,
  language,
  options
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  busy: boolean;
  canAsk: boolean;
  dictation: Dictation;
  language: AnswerLanguage;
  options: ReactNode;
}) {
  const stop = stopAction(dictation, busy, onStop);
  return (
    <form
      className="grid min-w-0 gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (canAsk) onSubmit();
      }}
      data-testid="ask-box"
    >
      <div className="grid gap-3 rounded-control border border-ink-1 bg-raised p-3 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-indigo sm:p-4">
        <label htmlFor="ask-question" className="sr-only">
          Your question
        </label>
        <textarea
          id="ask-question"
          value={value}
          maxLength={QUESTION_MAX}
          rows={2}
          dir="auto"
          readOnly={dictation.listening}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape" && dictation.listening) {
              event.preventDefault();
              dictation.stop();
              return;
            }
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              if (canAsk) onSubmit();
            }
          }}
          placeholder="Why does alum fix madder on cotton?"
          className="min-h-16 w-full resize-none bg-transparent px-1 font-reading text-lede text-ink-1 outline-none placeholder:text-ink-3"
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <DictationControl dictation={dictation} language={language} onStart={() => dictation.start(value)} />
          <ActionGroup inline align="end" className="max-sm:w-full">
            {stop ? (
              <Button variant="quiet" onClick={stop.act} aria-label={stop.label}>
                Stop
              </Button>
            ) : null}
            <Button type="submit" variant="primary" disabled={!canAsk}>
              Ask
            </Button>
          </ActionGroup>
        </div>
      </div>
      {options}
    </form>
  );
}
