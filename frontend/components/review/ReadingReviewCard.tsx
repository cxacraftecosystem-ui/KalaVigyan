import { FactSources } from "@/components/review/FactEvidence";
import { QueueDecisionBar } from "@/components/review/QueueDecisionBar";
import { QueueItemHeader } from "@/components/review/QueueItemHeader";
import { ReviewTerm } from "@/components/review/ReviewTerm";
import { envelopeLine, READING_ACTIONS, READING_OUTCOME, readingLine, readingTitle, stageLine } from "@/lib/readingReviewView";
import type { QueueAction, ReadingItem } from "@/lib/reviewQueueContract";

type Decide = (action: QueueAction, words: string) => Promise<string | null>;

export function ReadingReviewCard({ item, onDecide }: { item: ReadingItem; onDecide: Decide }) {
  const reading = item.reading;
  return (
    <article className="grid gap-4" data-testid="reading-review-card">
      <QueueItemHeader item={item} />
      <div className="grid max-w-measure gap-1">
        <h3 className="font-headline text-h3 text-ink-1">{readingTitle(reading)}</h3>
        <p className="font-ui text-label text-ink-2">{stageLine(reading)}</p>
      </div>
      <dl className="grid gap-x-6 gap-y-2 font-ui text-label sm:grid-cols-2">
        <ReviewTerm term="Read as" value={readingLine(reading)} />
        <ReviewTerm term="The stage's usual range" value={envelopeLine(reading)} />
      </dl>
      <p className="max-w-measure font-reading text-body text-ink-1">{reading.statement}</p>
      <FactSources sources={reading.sources} />
      <p className="max-w-measure font-ui text-ui text-ink-1">{READING_OUTCOME}</p>
      <QueueDecisionBar actions={READING_ACTIONS} onDecide={onDecide} />
    </article>
  );
}
