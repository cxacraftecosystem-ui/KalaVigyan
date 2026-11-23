import { CircleCheck } from "lucide-react";

import { QueueDecisionBar } from "@/components/review/QueueDecisionBar";
import { QueueItemHeader } from "@/components/review/QueueItemHeader";
import { ReviewTerm } from "@/components/review/ReviewTerm";
import { TextLink } from "@/components/ui/TextLink";
import { datasetReadLine } from "@/lib/datasetRecord";
import { LAYER_WRITES, layerTerms } from "@/lib/layerReviewView";
import type { LayerItem, QueueAction } from "@/lib/reviewQueueContract";
import { componentActions } from "@/lib/reviewQueueView";

type Decide = (action: QueueAction, words: string) => Promise<string | null>;

export function LayerReviewCard({ item, onDecide }: { item: LayerItem; onDecide: Decide }) {
  const review = item.layer;
  const dataset = review.dataset;
  const provenance = datasetReadLine(dataset);
  return (
    <article className="grid gap-4" data-testid="layer-review-card">
      <QueueItemHeader item={item} />
      <div className="grid max-w-measure gap-1">
        <h3 className="font-headline text-h3 text-ink-1">{dataset.title}</h3>
        <p className="font-code text-label text-ink-2">{dataset.code}</p>
        <p className="font-ui text-label text-ink-2">
          {dataset.landingUrl ? (
            <TextLink href={dataset.landingUrl} external>
              {dataset.publisher ?? dataset.landingUrl}
            </TextLink>
          ) : (
            dataset.publisher
          )}
        </p>
        {provenance ? <p className="font-ui text-caption text-ink-3">{provenance}</p> : null}
      </div>
      <dl className="grid gap-x-6 gap-y-2 font-ui text-label sm:grid-cols-2">
        {layerTerms(review).map((line) => (
          <ReviewTerm key={line.term} term={line.term} value={line.value} />
        ))}
      </dl>
      {dataset.citation ? <p className="max-w-measure font-reading text-body-sm text-ink-1">{dataset.citation}</p> : null}
      <section className="grid gap-2">
        <h4 className="font-ui text-h4 text-ink-1">Checks it passed</h4>
        <ul className="grid gap-2">
          {review.checks.map((check) => (
            <li key={check} className="flex items-center gap-2 font-ui text-ui text-ink-1">
              <CircleCheck className="h-4 w-4 shrink-0 text-success" aria-hidden />
              {check}
            </li>
          ))}
        </ul>
      </section>
      <p className="max-w-measure font-ui text-ui text-ink-1">{LAYER_WRITES}</p>
      <QueueDecisionBar actions={componentActions()} onDecide={onDecide} />
    </article>
  );
}
