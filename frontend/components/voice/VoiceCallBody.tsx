"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { SourcesList } from "@/components/answer/SourcesList";
import { FormAlert } from "@/components/auth/FormAlert";
import { useRevealRow } from "@/components/hooks/useRevealRow";
import { orbLabel, statusWord } from "@/components/voice/voiceWords";
import { VoiceOrb } from "@/components/voice/VoiceOrb";
import { VoiceTranscript } from "@/components/voice/VoiceTranscript";
import { VoiceTurnActions, type TurnActionContext } from "@/components/voice/VoiceTurnActions";
import type { AnswerLanguage } from "@/lib/answerLanguages";
import type { VoiceCall, VoiceCallState } from "@/lib/voiceCall";
import { conversationSourceNumbers, sourcesOfAnswer } from "@/lib/voiceConversation";

type Reveal = { answerId: string; nonce: number };

export type HostActions = Omit<TurnActionContext, "craftSlug" | "showSources">;

export function VoiceCallBody({ call, state, language, host }: { call: VoiceCall; state: VoiceCallState; language: AnswerLanguage | null; host: HostActions }) {
  const { conversation, session, activity } = state;
  const [revealed, setRevealed] = useState<Reveal | null>(null);
  const { registerRow, containerRef, reveal, flashKey } = useRevealRow();
  const numbers = useMemo(() => conversationSourceNumbers(conversation), [conversation]);
  const sourcesById = useMemo(() => new Map(conversation.sources.map((source) => [source.id, source])), [conversation.sources]);
  const entries = useMemo(
    () => [...numbers.entries()].sort((a, b) => a[1] - b[1]).map(([id, number]) => ({ id, number, source: sourcesById.get(id) ?? null })),
    [numbers, sourcesById]
  );
  const showSources = useCallback((answerId: string) => setRevealed((previous) => ({ answerId, nonce: (previous?.nonce ?? 0) + 1 })), []);
  const level = useCallback(() => call.level(), [call]);

  useEffect(() => {
    if (state.reveal) showSources(state.reveal.answerId);
  }, [showSources, state.reveal]);

  useEffect(() => {
    if (revealed) reveal("sources");
  }, [reveal, revealed]);

  const context: TurnActionContext = { ...host, craftSlug: session?.craft?.slug ?? null, showSources };
  const pressable = state.phase === "live" && session?.transport === "RELAY";
  const word = statusWord(state);
  const flashIds = flashKey === "sources" && revealed ? sourcesOfAnswer(conversation.turns, revealed.answerId) : undefined;

  return (
    <div ref={containerRef as React.RefObject<HTMLDivElement>} className="grid min-h-0 flex-1 gap-4 overflow-y-auto overscroll-contain px-4 py-4">
      {state.phase === "ended" || state.phase === "failed" ? null : (
        <div className="grid justify-items-center gap-3 py-2">
          <VoiceOrb activity={state.phase === "live" ? activity : "connecting"} level={level} label={orbLabel(activity) ?? word} onPress={pressable ? () => call.talk() : undefined} />
          <p role="status" className="min-h-5 text-center font-ui text-ui text-ink-2" data-testid="voice-status">
            {word}
          </p>
        </div>
      )}
      {state.phase === "failed" && state.message ? <FormAlert>{state.message}</FormAlert> : null}
      {state.phase === "ended" && state.message ? <p className="text-center font-ui text-ui text-ink-2">{state.message}</p> : null}
      {conversation.problem ? <FormAlert>{conversation.problem}</FormAlert> : null}
      <VoiceTranscript conversation={conversation} language={language} citing={{ numbers, sourcesById }} actions={(turn) => <VoiceTurnActions turn={turn} context={context} />} />
      {entries.length > 0 ? (
        <div ref={registerRow("sources")}>
          <SourcesList entries={entries} idPrefix="voice-source" compact flashIds={flashIds} />
        </div>
      ) : null}
    </div>
  );
}
