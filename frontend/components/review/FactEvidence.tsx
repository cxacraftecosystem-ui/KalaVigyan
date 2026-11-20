import { CircleCheck, CircleX } from "lucide-react";

import { TextLink } from "@/components/ui/TextLink";
import type { FactSource, GateCheck } from "@/lib/reviewQueueContract";
import { gateLine, suppliedLine } from "@/lib/reviewQueueView";

export function FactSources({ sources }: { sources: FactSource[] }) {
  return (
    <section className="grid gap-2">
      <h4 className="font-ui text-h4 text-ink-1">Sources</h4>
      <ul className="grid gap-3">
        {sources.map((source) => (
          <li key={`${source.title}-${source.url ?? ""}`} className="grid gap-1">
            <p className="font-ui text-ui text-ink-1">
              {source.url ? <TextLink href={source.url} external>{source.title}</TextLink> : source.title}
            </p>
            <p className="font-ui text-caption text-ink-3">
              Reliability {source.reliability}
              {source.licence ? ` · ${source.licence}` : ""}
            </p>
            {source.supplied ? <p className="font-ui text-caption text-ink-2">{suppliedLine(source.supplied)}</p> : null}
            {source.quotes.map((quote) => (
              <blockquote key={`${quote.text}-${quote.locator ?? ""}`} className="border-s-2 border-rule-strong ps-3">
                <p className="font-reading text-quote italic text-ink-1">{quote.text}</p>
                {quote.locator ? <p className="font-ui text-caption text-ink-3">{quote.locator}</p> : null}
              </blockquote>
            ))}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function FactChecks({ gates }: { gates: GateCheck[] }) {
  return (
    <section className="grid gap-2">
      <h4 className="font-ui text-h4 text-ink-1">Automatic checks</h4>
      <ul className="grid gap-2">
        {gates.map((check) => (
          <li key={check.gate} className="grid gap-1">
            <p className="flex items-center gap-2 font-ui text-ui text-ink-1">
              {check.passed ? <CircleCheck className="h-4 w-4 shrink-0 text-success" aria-hidden /> : <CircleX className="h-4 w-4 shrink-0 text-error" aria-hidden />}
              {gateLine(check)}
            </p>
            {check.reasons.map((reason) => (
              <p key={reason} className="font-ui text-label text-ink-2">
                {reason}
              </p>
            ))}
            {check.related.map((related) => (
              <p key={related.id} className="font-ui text-label text-ink-2">
                Close to: {related.text}
              </p>
            ))}
          </li>
        ))}
      </ul>
    </section>
  );
}
