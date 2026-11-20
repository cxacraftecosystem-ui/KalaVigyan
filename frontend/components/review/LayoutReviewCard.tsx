import { DeliveredComponentView } from "@/components/review/DeliveredComponentView";
import { LayoutChangeList } from "@/components/review/LayoutChangeList";
import { QueueDecisionBar } from "@/components/review/QueueDecisionBar";
import { QueueItemHeader } from "@/components/review/QueueItemHeader";
import { TextLink } from "@/components/ui/TextLink";
import { layoutActions, subjectLine, versionLine } from "@/lib/layoutReviewView";
import type { LayoutItem, PlacedDelivery, QueueAction } from "@/lib/reviewQueueContract";

type Decide = (action: QueueAction, words: string) => Promise<string | null>;

export function LayoutReviewCard({ item, onDecide }: { item: LayoutItem; onDecide: Decide }) {
  const review = item.layout;
  return (
    <article className="grid gap-4" data-testid="layout-review-card">
      <QueueItemHeader item={item} />
      <div className="grid max-w-measure gap-1">
        <h3 className="font-headline text-h3 text-ink-1">
          {item.craft ? review.subjectName : <TextLink href={review.pageUrl}>{review.subjectName}</TextLink>}
        </h3>
        <p className="font-ui text-label text-ink-2">{subjectLine(review)}</p>
        {review.note ? <p className="font-reading text-body-sm text-ink-1">{review.note}</p> : null}
      </div>
      <p className="max-w-measure font-ui text-ui text-ink-1">{versionLine(review)}</p>
      <LayoutChangeList changes={review.changes} />
      {review.placed?.length ? <PlacedComponents placed={review.placed} /> : null}
      <QueueDecisionBar actions={layoutActions(review)} onDecide={onDecide} />
    </article>
  );
}

function PlacedComponents({ placed }: { placed: PlacedDelivery[] }) {
  return (
    <section className="grid gap-6" data-testid="layout-placed-components">
      <h4 className="font-ui text-h4 text-ink-1">Components it places that wait in the queue</h4>
      {placed.map((part) => (
        <div key={part.label} className="grid gap-2 border-t border-ink-1 pt-3">
          <p className="font-headline text-h3 text-ink-1">{part.title}</p>
          <p className="font-code text-label text-ink-2 [overflow-wrap:anywhere]">{part.label}</p>
          <DeliveredComponentView label={part.label} delivery={part.delivery} />
        </div>
      ))}
    </section>
  );
}
