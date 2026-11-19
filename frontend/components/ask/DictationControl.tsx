"use client";

import { motion } from "framer-motion";
import { Mic } from "lucide-react";

import type { Dictation } from "@/components/ask/useDictation";
import { soundBar } from "@/components/guide/guideMotion";
import { useAppReducedMotion } from "@/components/guide/useAppReducedMotion";
import type { AnswerLanguage } from "@/lib/answerLanguages";
import { listeningLabel } from "@/lib/dictation";
import { cn } from "@/lib/utils";

const BARS = [0, 1, 2, 3, 4];

function SoundBars() {
  const reduce = useAppReducedMotion();
  return (
    <span className="hidden h-6 items-center gap-1 sm:flex" aria-hidden>
      {BARS.map((index) => (
        <motion.span key={index} initial={false} {...soundBar(reduce, index)} className="h-[22px] w-1 origin-center rounded-full bg-ink-2" />
      ))}
    </span>
  );
}

function MicButton({ listening, language, onPress }: { listening: boolean; language: AnswerLanguage; onPress: () => void }) {
  const label = listening ? "Stop dictation" : `Dictate in ${language.label}`;
  return (
    <button
      type="button"
      onClick={onPress}
      aria-label={label}
      aria-pressed={listening}
      title={label}
      data-testid="dictate-button"
      className={cn(
        "grid h-11 w-11 shrink-0 place-items-center rounded-full transition-colors duration-state",
        listening ? "bg-indigo text-indigo-on hover:bg-indigo-hover" : "border border-rule-strong bg-raised text-ink-2 hover:bg-sunk hover:text-ink-1"
      )}
    >
      <Mic className={listening ? "h-[18px] w-[18px]" : "h-5 w-5"} aria-hidden />
    </button>
  );
}

export function DictationControl({ dictation, language, onStart }: { dictation: Dictation; language: AnswerLanguage; onStart: () => void }) {
  const { listening, offered, failure } = dictation;
  const said = listening ? listeningLabel(language) : failure;
  return (
    <div className="flex min-w-0 items-center gap-3">
      {listening || offered ? <MicButton listening={listening} language={language} onPress={listening ? dictation.stop : onStart} /> : null}
      {listening ? <SoundBars /> : null}
      <span role="status" dir="auto" className={cn("min-w-0 font-ui text-ui", listening ? "truncate font-semibold text-ink-1" : "text-ink-3", !said && "sr-only")}>
        {said}
      </span>
    </div>
  );
}
