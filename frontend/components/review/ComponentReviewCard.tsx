import { DeliveredComponentView } from "@/components/review/DeliveredComponentView";
import { QueueDecisionBar } from "@/components/review/QueueDecisionBar";
import { QueueItemHeader } from "@/components/review/QueueItemHeader";
import { ReviewTerm } from "@/components/review/ReviewTerm";
import type { ClosestComponent, ComponentItem, QueueAction } from "@/lib/reviewQueueContract";
import { codeLabel, componentActions, fieldsLine, overlapLine } from "@/lib/reviewQueueView";

type Decide = (action: QueueAction, words: string) => Promise<string | null>;

export function ComponentReviewCard({ item, onDecide }: { item: ComponentItem; onDecide: Decide }) {
  const proposal = item.component;
  return (
    <article className="grid gap-4" data-testid="component-review-card">
      <QueueItemHeader item={item} />
      <div className="grid max-w-measure gap-1">
        <h3 className="font-headline text-h3 text-ink-1">{proposal.title}</h3>
        <p className="font-code text-label text-ink-2">{proposal.label}</p>
        <p className="font-reading text-body-sm text-ink-1">{proposal.description}</p>
      </div>
      <dl className="grid gap-x-6 gap-y-2 font-ui text-label sm:grid-cols-2">
        <ReviewTerm term="Kind" value={codeLabel(proposal.kind)} />
        <ReviewTerm term="Field" value={fieldsLine(proposal.field, proposal.fields) ?? codeLabel(proposal.field)} />
        <ReviewTerm term="For" value={proposal.subjects.map((subject) => `${codeLabel(subject.kind)} ${subject.key}`).join(", ")} />
        {proposal.extends ? <ReviewTerm term={`${codeLabel(proposal.extension ?? "Extends")} of`} value={proposal.extends} /> : null}
        <ReviewTerm term="Library components considered" value={proposal.consideredLabels.join(", ") || "None named"} />
      </dl>
      {proposal.delivery ? <DeliveredComponentView label={proposal.label} delivery={proposal.delivery} /> : null}
      <ClosestMatches closest={proposal.closest} />
      <QueueDecisionBar actions={componentActions()} onDecide={onDecide} />
    </article>
  );
}

function ClosestMatches({ closest }: { closest: ClosestComponent[] }) {
  if (!closest.length) {
    return <p className="font-ui text-ui text-ink-2">The library holds nothing close to it.</p>;
  }
  return (
    <section className="grid gap-2">
      <h4 className="font-ui text-h4 text-ink-1">Closest in the library</h4>
      <ul className="grid gap-3">
        {closest.map((match) => (
          <li key={match.component.label} className="grid gap-0.5">
            <p className="font-ui text-ui text-ink-1">{match.component.title}</p>
            <p className="font-code text-caption text-ink-3">{match.component.label}</p>
            <p className="font-ui text-label text-ink-2">
              {overlapLine(match.overlap)}
              {match.reasons.length ? ` · ${match.reasons.join("; ")}` : ""}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
