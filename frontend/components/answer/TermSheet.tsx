"use client";

import { useEffect, useMemo } from "react";
import { CircleAlert } from "lucide-react";

import { CitationProvider, type CitationLookup } from "@/components/answer/CitationContext";
import { ExplainerSentence } from "@/components/answer/ExplainerSentence";
import { SignInLink } from "@/components/auth/SignInLink";
import { FieldDialog } from "@/components/dialogs/FieldDialog";
import { failureMessage, useRemote, type RemoteFailure } from "@/components/hooks/useRemote";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import type { TermSpan } from "@/lib/explainerBlockBase";
import type { Term } from "@/lib/explainerContract";
import { fetchTerm } from "@/lib/termSummary";

type Looked = { key: string; term: Term | null };

function useTermSummary(span: TermSpan | null, language: string) {
  const load = useMemo(() => (span ? (): Promise<Looked> => fetchTerm(span.termKey, language).then((term) => ({ key: span.termKey, term })) : null), [span, language]);
  return useRemote(load);
}

function needsSignIn(failure: RemoteFailure | null): boolean {
  return failure?.cause instanceof ApiError && failure.cause.status === 401;
}

function termLookup(term: Term): CitationLookup {
  return { numbers: new Map(term.sources.map((source, index) => [source.id, index + 1])), sourcesById: new Map(term.sources.map((source) => [source.id, source])) };
}

function TermBody({ term }: { term: Term }) {
  const lookup = useMemo(() => termLookup(term), [term]);
  return (
    <CitationProvider value={lookup}>
      <p className="mt-3 font-reading text-body-sm text-ink-1" data-testid="term-summary">
        {term.summary.map((sentence) => (
          <ExplainerSentence key={sentence.id} sentence={{ ...sentence, terms: [] }} />
        ))}
      </p>
    </CitationProvider>
  );
}

function TermFailure({ failure, onRetry }: { failure: RemoteFailure; onRetry: () => void }) {
  return (
    <div role="alert" className="mt-3 grid gap-3 rounded-control bg-error-wash px-3 py-2.5 font-ui text-ui text-ink-1">
      <p className="flex items-start gap-2">
        <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-error" aria-hidden />
        {failureMessage(failure, "Couldn't load this term.")}
      </p>
      {needsSignIn(failure) ? (
        <SignInLink variant="quiet" />
      ) : (
        <ActionGroup align="start">
          <Button variant="quiet" size="sm" onClick={onRetry}>
            Try again
          </Button>
        </ActionGroup>
      )}
    </div>
  );
}

export function TermSheet({
  span,
  language,
  onClose,
  onMissing,
  onAsk
}: {
  span: TermSpan | null;
  language: string;
  onClose: () => void;
  onMissing: (termKey: string) => void;
  onAsk: ((term: Term) => void) | null;
}) {
  const remote = useTermSummary(span, language);
  const looked = remote.data && span && remote.data.key === span.termKey ? remote.data : null;
  const term = looked?.term ?? null;
  const missing = looked !== null && term === null;

  useEffect(() => {
    if (missing && span) onMissing(span.termKey);
  }, [missing, span, onMissing]);

  return (
    <FieldDialog
      open={span !== null && !missing}
      onClose={onClose}
      title={term?.label ?? span?.text ?? ""}
      description={term && term.localNames.length > 0 ? `Also called ${term.localNames.join(", ")}` : undefined}
      className="max-w-lg"
      footer={
        <>
          {term && onAsk ? <Button onClick={() => onAsk(term)}>Ask about it</Button> : null}
          <Button variant="quiet" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      {term ? <TermBody term={term} /> : null}
      {!term && !remote.failure ? (
        <p role="status" className="mt-3 flex items-center gap-2 font-ui text-ui text-ink-3">
          <span className="kv-spin" aria-hidden />
          Looking it up…
        </p>
      ) : null}
      {remote.failure ? <TermFailure failure={remote.failure} onRetry={remote.retry} /> : null}
    </FieldDialog>
  );
}
