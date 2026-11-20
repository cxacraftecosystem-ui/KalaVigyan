import { FactChecks, FactSources } from "@/components/review/FactEvidence";
import { QueueDecisionBar } from "@/components/review/QueueDecisionBar";
import { QueueItemHeader } from "@/components/review/QueueItemHeader";
import { ReviewTerm } from "@/components/review/ReviewTerm";
import { TextLink } from "@/components/ui/TextLink";
import type { QueueAction, RelatedFact, StructureItem } from "@/lib/reviewQueueContract";
import { codeLabel } from "@/lib/reviewQueueView";
import { checkLines, entryLines, STRUCTURE_KIND_LABELS, structureActions, targetLine, writesLine } from "@/lib/structureReviewView";

type Decide = (action: QueueAction, words: string) => Promise<string | null>;

export function StructureReviewCard({ item, onDecide }: { item: StructureItem; onDecide: Decide }) {
  const review = item.structure;
  return (
    <article className="grid gap-4" data-testid="structure-review-card">
      <QueueItemHeader item={item} />
      <div className="grid max-w-measure gap-1">
        <h3 className="font-headline text-h3 text-ink-1">{STRUCTURE_KIND_LABELS[review.kind]}</h3>
        <p className="font-ui text-label text-ink-2">
          <TextLink href={review.pageUrl}>{targetLine(review)}</TextLink>
        </p>
        {review.note ? <p className="font-reading text-body-sm text-ink-1">{review.note}</p> : null}
      </div>
      <dl className="grid gap-x-6 gap-y-2 font-ui text-label sm:grid-cols-2">
        {entryLines(review.item).map((line) => (
          <ReviewTerm key={line.term} term={line.term} value={line.value} lang={line.lang} script={line.script} />
        ))}
        {review.current ? <ReviewTerm term="On the page now" value={review.current} /> : null}
        {review.field ? <ReviewTerm term="Field" value={codeLabel(review.field)} /> : null}
      </dl>
      {review.statement ? <p className="max-w-measure font-reading text-body text-ink-1">{review.statement}</p> : null}
      {review.conflicting.length ? <Disagreeing facts={review.conflicting} /> : null}
      {review.sources.length || review.checks.length ? (
        <div className="grid gap-5 md:grid-cols-2">
          {review.sources.length ? <FactSources sources={review.sources} /> : null}
          {review.checks.length ? <FactChecks gates={checkLines(review.checks)} /> : null}
        </div>
      ) : null}
      <p className="max-w-measure font-ui text-ui text-ink-1">{writesLine(review)}</p>
      <QueueDecisionBar actions={structureActions(review)} onDecide={onDecide} />
    </article>
  );
}

function Disagreeing({ facts }: { facts: RelatedFact[] }) {
  return (
    <section className="grid max-w-measure gap-2">
      <h4 className="font-ui text-h4 text-ink-1">The facts that disagree</h4>
      <ul className="grid gap-2 border-s-2 border-madder ps-3">
        {facts.map((fact) => (
          <li key={fact.id} className="font-reading text-body-sm text-ink-1">
            {fact.text}
          </li>
        ))}
      </ul>
    </section>
  );
}
