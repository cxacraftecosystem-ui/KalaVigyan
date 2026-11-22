"use client";

import type { ReactNode } from "react";

import { Field, TextInput } from "@/components/FormControls";
import { NO_CAP } from "@/lib/aiBudgetContract";

type CapFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  busy: boolean;
  hint?: string;
  error?: string;
  step?: string;
  fieldKey?: string;
};

export function CapField({ label, value, onChange, busy, hint, error, step = "any", fieldKey }: CapFieldProps) {
  return (
    <Field label={label} hint={hint} error={error} fieldKey={fieldKey}>
      <TextInput
        type="number"
        inputMode="decimal"
        min={0}
        step={step}
        placeholder={NO_CAP}
        value={value}
        disabled={busy}
        onChange={(event) => onChange(event.target.value)}
      />
    </Field>
  );
}

export function BudgetGroup({ id, title, note, children }: { id: string; title: string; note: string; children: ReactNode }) {
  return (
    <div role="group" className="grid min-w-0 gap-4 border-t border-rule pt-5" aria-labelledby={`${id}-title`}>
      <div className="grid max-w-measure gap-1">
        <h3 id={`${id}-title`} className="font-headline text-h4 text-ink-1">
          {title}
        </h3>
        <p className="font-ui text-label text-ink-2">{note}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{children}</div>
    </div>
  );
}
