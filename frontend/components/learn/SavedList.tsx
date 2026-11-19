"use client";

import Link from "next/link";

import { EmptyState } from "@/components/EmptyState";
import { RowFacts, type RowFact } from "@/components/learn/RowFacts";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Badge } from "@/components/ui/Badge";
import { Button, buttonLook } from "@/components/ui/button";
import { languageName } from "@/lib/craftRecord";
import { DISCIPLINE_LABEL } from "@/lib/explainerView";
import { formatDate } from "@/lib/format";
import { hasNewerVersion, type SavedExplainer } from "@/lib/learningContract";
import { ASK_PATH, explainerHref } from "@/lib/savedView";

export const SAVED_EMPTY_TITLE = "Your saved answers";
export const SAVED_EMPTY_BODY = "Save an answer and it waits here with its version, and a note when its sources grow.";

function savedFacts(item: SavedExplainer): RowFact[] {
  const facts: (RowFact | null)[] = [
    item.craft ? { label: "Craft", value: item.craft.name } : null,
    item.facets.length > 0 ? { label: "About", value: item.facets.map((facet) => DISCIPLINE_LABEL[facet]).join(", ") } : null,
    { label: "Language", value: languageName(item.language) },
    { label: "Version", value: item.latestVersion },
    { label: "Saved", value: formatDate(item.savedAt) },
    item.checkedAt ? { label: "Checked", value: formatDate(item.checkedAt) } : null
  ];
  return facts.filter((fact): fact is RowFact => fact !== null);
}

function SavedRow({ item, busy, onRemove }: { item: SavedExplainer; busy: boolean; onRemove: (id: string) => void }) {
  return (
    <li className="grid min-w-0 gap-3 border-b border-rule py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-6" data-testid="saved-explainer">
      <div className="grid min-w-0 gap-1.5">
        <h3 className="min-w-0 font-reading text-h3 [overflow-wrap:anywhere]">
          <Link href={explainerHref(item.explainerId)} className="kv-link font-normal">
            {item.question}
          </Link>
        </h3>
        <RowFacts facts={savedFacts(item)} />
        {hasNewerVersion(item) ? (
          <span data-testid="saved-newer">
            <Badge>Newer version</Badge>
          </span>
        ) : null}
      </div>
      <ActionGroup inline align="end">
        <Button type="button" variant="quiet" size="sm" disabled={busy} busy={busy} busyLabel="Removing" onClick={() => onRemove(item.explainerId)} data-testid="saved-remove">
          Remove<span className="sr-only"> {item.question}</span>
        </Button>
      </ActionGroup>
    </li>
  );
}

export function SavedList({ items, busy, onRemove }: { items: readonly SavedExplainer[]; busy: string | null; onRemove: (id: string) => void }) {
  if (items.length === 0) {
    return (
      <div data-testid="saved-empty">
        <EmptyState
          headingLevel={3}
          title={SAVED_EMPTY_TITLE}
          body={SAVED_EMPTY_BODY}
          actions={
            <Link href={ASK_PATH} {...buttonLook({ variant: "primary" })}>
              Ask a question
            </Link>
          }
        />
      </div>
    );
  }
  return (
    <ul className="grid min-w-0 border-t border-ink-1" data-testid="saved-list">
      {items.map((item) => (
        <SavedRow key={item.explainerId} item={item} busy={busy === item.explainerId} onRemove={onRemove} />
      ))}
    </ul>
  );
}
