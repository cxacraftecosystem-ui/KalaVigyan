"use client";

import { useId, type ChangeEvent } from "react";

import { Field, FieldBlock, FieldMessages, Select, TextArea, TextInput } from "@/components/FormControls";
import { sourceKindLabel } from "@/lib/citations";
import { SOURCE_AUTHOR_MAX, SOURCE_AUTHORS_MAX, SOURCE_CONTAINER_MAX, SOURCE_KINDS, SOURCE_TITLE_MAX } from "@/lib/stagedReviewContract";
import type { SourceDraft } from "@/lib/stagedReviewView";

const HINT = "Leave a field empty to keep what the source holds.";

type TextField = "title" | "authors" | "year" | "containerTitle";

export function StagedSourceFields({ draft, problem, onChange }: { draft: SourceDraft; problem: string | null; onChange: (next: SourceDraft) => void }) {
  const id = useId();
  const set = (field: TextField) => (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onChange({ ...draft, [field]: event.target.value });
  return (
    <FieldBlock label="Corrected fields" hint={<FieldMessages id={id} hint={HINT} error={problem ?? undefined} />}>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Title">
          <TextInput value={draft.title} maxLength={SOURCE_TITLE_MAX} onChange={set("title")} />
        </Field>
        <Field label="Journal or book">
          <TextInput value={draft.containerTitle} maxLength={SOURCE_CONTAINER_MAX} onChange={set("containerTitle")} />
        </Field>
        <Field label="Authors" hint="One author on each line.">
          <TextArea value={draft.authors} rows={3} maxLength={SOURCE_AUTHORS_MAX * (SOURCE_AUTHOR_MAX + 1)} onChange={set("authors")} />
        </Field>
        <div className="grid content-start gap-4">
          <Field label="Year">
            <TextInput value={draft.year} inputMode="numeric" maxLength={4} onChange={set("year")} />
          </Field>
          <Field label="Kind of source">
            <Select value={draft.kind} onChange={(event) => onChange({ ...draft, kind: event.target.value })}>
              <option value="">As the source holds it</option>
              {SOURCE_KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {sourceKindLabel(kind)}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </div>
    </FieldBlock>
  );
}
