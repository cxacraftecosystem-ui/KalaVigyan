"use client";

import { useState } from "react";

import { ClientIdentity } from "@/components/oauth/ClientIdentity";
import { ScopeChoices } from "@/components/oauth/ScopeChoices";
import { TermsAcceptance } from "@/components/oauth/TermsAcceptance";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { consentProblem, initialScopes, withScope } from "@/lib/oauthConsent";
import type { AuthorizationPrompt, McpScope, TermsOfUse } from "@/lib/oauthContract";

export function ConsentForm({
  prompt,
  terms,
  busy,
  error,
  onApprove,
  onCancel
}: {
  prompt: AuthorizationPrompt;
  terms: TermsOfUse | null;
  busy: boolean;
  error: string | null;
  onApprove: (chosen: McpScope[]) => void;
  onCancel: () => void;
}) {
  const [chosen, setChosen] = useState<McpScope[]>(() => initialScopes(prompt));
  const [ticked, setTicked] = useState(false);
  const problem = consentProblem(prompt, ticked);

  return (
    <form
      className="grid max-w-measure gap-6"
      data-testid="consent-form"
      onSubmit={(event) => {
        event.preventDefault();
        if (!problem) onApprove(chosen);
      }}
    >
      <ClientIdentity prompt={prompt} />
      <ScopeChoices
        choices={prompt.scopes}
        chosen={chosen}
        disabled={busy}
        onChange={(scope, on) => setChosen((current) => withScope(current, scope, on))}
      />
      <TermsAcceptance status={prompt.terms} terms={terms} ticked={ticked} disabled={busy} onTick={setTicked} />
      {error ? (
        <p role="alert" className="text-ui font-ui text-error">
          {error}
        </p>
      ) : null}
      <ActionGroup align="start">
        <Button type="submit" busy={busy} busyLabel="Connecting" disabled={problem !== null}>
          Approve
        </Button>
        <Button type="button" variant="quiet" disabled={busy} onClick={onCancel}>
          Cancel
        </Button>
      </ActionGroup>
      {problem ? <p className="text-label font-ui text-ink-3">{problem}</p> : null}
    </form>
  );
}
