import type { ReactNode } from "react";

export type RowFact = { label: string; value: ReactNode };

export function RowFacts({ facts }: { facts: readonly RowFact[] }) {
  if (facts.length === 0) return null;
  return (
    <dl className="flex min-w-0 flex-wrap gap-x-5 gap-y-1 font-ui text-label lining-nums tabular-nums">
      {facts.map((fact) => (
        <div key={fact.label} className="flex min-w-0 max-w-full gap-1.5">
          <dt className="shrink-0 text-ink-3">{fact.label}</dt>{" "}
          <dd className="min-w-0 text-ink-1 [overflow-wrap:anywhere]">{fact.value}</dd>
        </div>
      ))}
    </dl>
  );
}
