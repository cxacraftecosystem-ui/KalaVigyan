"use client";

import { useId, useState } from "react";
import { CircleAlert } from "lucide-react";

import { CiteAnswer } from "@/components/answer/CiteAnswer";
import type { CitedAnswer } from "@/lib/answerCitation";
import { useAnswerSaved, type AnswerSaved } from "@/components/answer/useAnswerSaved";
import { useAuth } from "@/components/AuthProvider";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { canSaveExport } from "@/lib/permissions";

function ActionsRow({ answer, save }: { answer: CitedAnswer; save: AnswerSaved | null }) {
  const [citing, setCiting] = useState(false);
  const panelId = useId();
  return (
    <div className="mt-7" data-testid="answer-actions">
      <ActionGroup align="start">
        {save ? (
          <Button variant="quiet" size="sm" aria-pressed={save.saved} disabled={!save.known} busy={save.busy} busyLabel={save.saved ? "Removing" : "Saving"} onClick={save.toggle} data-testid="save-answer">
            {save.saved ? "Saved" : "Save"}
          </Button>
        ) : null}
        <Button variant="quiet" size="sm" aria-expanded={citing} aria-controls={citing ? panelId : undefined} onClick={() => setCiting((open) => !open)} data-testid="cite-answer-toggle">
          Cite this answer
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

function SavingRow({ answer }: { answer: CitedAnswer }) {
  const save = useAnswerSaved(answer.explainerId);
  return <ActionsRow answer={answer} save={save} />;
}

export function AnswerActions({ answer }: { answer: CitedAnswer | null }) {
  const canSave = canSaveExport(useAuth().user);
  if (!answer) return null;
  return canSave ? <SavingRow answer={answer} /> : <ActionsRow answer={answer} save={null} />;
}
