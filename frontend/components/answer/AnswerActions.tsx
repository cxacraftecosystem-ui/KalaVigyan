"use client";

import { useId, useState } from "react";
import { CircleAlert } from "lucide-react";

import { CiteAnswer } from "@/components/answer/CiteAnswer";
import type { CitedAnswer } from "@/lib/answerCitation";
import type { AnswerLanguage } from "@/lib/answerLanguages";
import { useAnswerSaved, type AnswerSaved } from "@/components/answer/useAnswerSaved";
import { useAuth } from "@/components/AuthProvider";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { ACTIONS_ENGLISH, ACTIONS_KEY, wordAttributes, wordedIn, type ActionWord, type Worded } from "@/lib/interfaceWords";
import { canSaveExport } from "@/lib/permissions";

type RowProps = { answer: CitedAnswer; save: AnswerSaved | null; worded: Worded<ActionWord> };

function Label({ language, children }: { language: AnswerLanguage | null; children: string }) {
  return language ? <span {...wordAttributes(language)}>{children}</span> : <>{children}</>;
}

function ActionsRow({ answer, save, worded }: RowProps) {
  const [citing, setCiting] = useState(false);
  const panelId = useId();
  const { words, language } = worded;
  return (
    <div className="mt-7" data-testid="answer-actions">
      <ActionGroup align="start">
        {save ? (
          <Button variant="quiet" size="sm" aria-pressed={save.saved} disabled={!save.known} busy={save.busy} busyLabel={save.saved ? words.removing : words.saving} onClick={save.toggle} data-testid="save-answer">
            <Label language={language}>{save.saved ? words.saved : words.save}</Label>
          </Button>
        ) : null}
        <Button variant="quiet" size="sm" aria-expanded={citing} aria-controls={citing ? panelId : undefined} onClick={() => setCiting((open) => !open)} data-testid="cite-answer-toggle">
          <Label language={language}>{words.cite}</Label>
        </Button>
      </ActionGroup>
      {save?.error ? (
        <p role="alert" className="mt-2 flex items-start gap-1.5 font-ui text-label text-error">
          <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          {save.error}
        </p>
      ) : null}
      {citing ? <CiteAnswer id={panelId} answer={answer} /> : null}
    </div>
  );
}

function SavingRow({ answer, worded }: { answer: CitedAnswer; worded: Worded<ActionWord> }) {
  const save = useAnswerSaved(answer.explainerId);
  return <ActionsRow answer={answer} save={save} worded={worded} />;
}

export function AnswerActions({ answer, language = null }: { answer: CitedAnswer | null; language?: AnswerLanguage | null }) {
  const canSave = canSaveExport(useAuth().user);
  if (!answer) return null;
  const worded = wordedIn(language, ACTIONS_KEY, ACTIONS_ENGLISH);
  return canSave ? <SavingRow answer={answer} worded={worded} /> : <ActionsRow answer={answer} save={null} worded={worded} />;
}
