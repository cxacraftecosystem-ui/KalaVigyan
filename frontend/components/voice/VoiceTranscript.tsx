"use client";

import type { ReactNode } from "react";

import { SectionBlock } from "@/components/answer/AnswerSectionBlock";
import { useAppReducedMotion } from "@/components/guide/useAppReducedMotion";
import { attributesForText, type AnswerLanguage } from "@/lib/answerLanguages";
import type { AnswerSentence, Citation, SourceRef } from "@/lib/types";
import type { VoiceConversation } from "@/lib/voiceConversation";
import type { VoiceTurn } from "@/lib/voiceContract";

type Citing = { numbers: Map<string, number>; sourcesById: Map<string, SourceRef>; onOpen: (citations: readonly Citation[]) => void };

function Heard({ text, language }: { text: string; language: AnswerLanguage | null }) {
  const shown = attributesForText(text, language);
  return (
    <p className="max-w-[85%] justify-self-end rounded-card bg-sunk px-3 py-2 font-ui text-ui font-normal text-ink-1">
      <span className="sr-only">You: </span>
      <span lang={shown.lang} dir={shown.dir}>
        {text}
      </span>
    </p>
  );
}

function Reply({ id, sentences, spoken, language, citing }: { id: string; sentences: AnswerSentence[]; spoken: string | null; language: AnswerLanguage | null; citing: Citing }) {
  const reduce = useAppReducedMotion();
  if (sentences.length > 0) {
    return <SectionBlock section={{ id, heading: "", sentences }} reduce={reduce} compact language={language} {...citing} />;
  }
  if (!spoken) return null;
  const shown = attributesForText(spoken, language);
  return (
    <p lang={shown.lang} dir={shown.dir} className="font-reading text-body-sm text-ink-2">
      {spoken}
    </p>
  );
}

export function VoiceTranscript({
  conversation,
  language,
  citing,
  actions
}: {
  conversation: VoiceConversation;
  language: AnswerLanguage | null;
  citing: Citing;
  actions: (turn: VoiceTurn) => ReactNode;
}) {
  const { turns, draft, heardLive } = conversation;
  if (turns.length === 0 && !draft?.heard && !heardLive) return null;
  return (
    <ol className="grid gap-4" aria-label="Transcript" data-testid="voice-transcript">
      {turns.map((turn) => (
        <li key={turn.turnId} className="grid gap-2">
          <Heard text={turn.heard} language={language} />
          <Reply id={turn.turnId} sentences={turn.sentences} spoken={turn.spoken} language={language} citing={citing} />
          {actions(turn)}
        </li>
      ))}
      {draft?.heard ? (
        <li className="grid gap-2">
          <Heard text={draft.heard} language={language} />
          <Reply id="draft" sentences={draft.sentences} spoken={null} language={language} citing={citing} />
        </li>
      ) : null}
      {heardLive ? (
        <li className="grid">
          <Heard text={heardLive} language={language} />
        </li>
      ) : null}
    </ol>
  );
}
