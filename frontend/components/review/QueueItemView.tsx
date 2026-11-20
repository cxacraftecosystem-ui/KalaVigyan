import { ComponentReviewCard } from "@/components/review/ComponentReviewCard";
import { FactReviewCard } from "@/components/review/FactReviewCard";
import { LayoutReviewCard } from "@/components/review/LayoutReviewCard";
import { PictureReviewCard } from "@/components/review/PictureReviewCard";
import { QueueItemHeader } from "@/components/review/QueueItemHeader";
import { ReviewCard } from "@/components/review/ReviewCard";
import { StructureReviewCard } from "@/components/review/StructureReviewCard";
import type { QueueAction, QueueItem } from "@/lib/reviewQueueContract";
import { isOpenItem, STATUS_LABELS } from "@/lib/testimonyContract";

export type QueueHandlers = {
  decide: (item: QueueItem, action: QueueAction, words: string) => Promise<string | null>;
  decidedElsewhere: () => void;
};

export function QueueItemView({ item, handlers }: { item: QueueItem; handlers: QueueHandlers }) {
  if (item.kind === "FACTS") return <FactReviewCard item={item} onDecide={(action, words) => handlers.decide(item, action, words)} />;
  if (item.kind === "COMPONENTS") return <ComponentReviewCard item={item} onDecide={(action, words) => handlers.decide(item, action, words)} />;
  if (item.kind === "LAYOUTS") return <LayoutReviewCard item={item} onDecide={(action, words) => handlers.decide(item, action, words)} />;
  if (item.kind === "STRUCTURE") return <StructureReviewCard item={item} onDecide={(action, words) => handlers.decide(item, action, words)} />;
  return (
    <div className="grid gap-3">
      <QueueItemHeader item={item} />
      <ul className="grid">{item.kind === "IMAGES" ? <PictureReviewCard item={item.picture} onDecided={handlers.decidedElsewhere} /> : <TestimonyEntry item={item.testimony} onDecided={handlers.decidedElsewhere} />}</ul>
    </div>
  );
}

function TestimonyEntry({ item, onDecided }: { item: Extract<QueueItem, { kind: "TESTIMONY" }>["testimony"]; onDecided: () => void }) {
  if (isOpenItem(item)) return <ReviewCard item={item} onDecided={onDecided} />;
  return (
    <li className="font-ui text-ui text-ink-2">
      {STATUS_LABELS[item.status]} · {item.craft.name}
    </li>
  );
}
