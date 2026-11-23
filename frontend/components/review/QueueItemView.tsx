import { ComponentReviewCard } from "@/components/review/ComponentReviewCard";
import { FactReviewCard } from "@/components/review/FactReviewCard";
import { LayerReviewCard } from "@/components/review/LayerReviewCard";
import { LayoutReviewCard } from "@/components/review/LayoutReviewCard";
import { PictureReviewCard } from "@/components/review/PictureReviewCard";
import { QueueItemHeader } from "@/components/review/QueueItemHeader";
import { ReadingReviewCard } from "@/components/review/ReadingReviewCard";
import { ReviewCard } from "@/components/review/ReviewCard";
import { StageReviewCard } from "@/components/review/StageReviewCard";
import { StructureReviewCard } from "@/components/review/StructureReviewCard";
import type { Filing, QueueAction, QueueItem } from "@/lib/reviewQueueContract";
import { isOpenItem, STATUS_LABELS } from "@/lib/testimonyContract";

export type QueueHandlers = {
  decide: (item: QueueItem, action: QueueAction, words: string, filing?: Filing | null) => Promise<string | null>;
  decidedElsewhere: () => void;
};

export function QueueItemView({ item, handlers }: { item: QueueItem; handlers: QueueHandlers }) {
  if (item.kind === "FACTS") return <FactReviewCard item={item} onDecide={(action, words, filing) => handlers.decide(item, action, words, filing)} />;
  if (item.kind === "COMPONENTS") return <ComponentReviewCard item={item} onDecide={(action, words) => handlers.decide(item, action, words)} />;
  if (item.kind === "LAYOUTS") return <LayoutReviewCard item={item} onDecide={(action, words) => handlers.decide(item, action, words)} />;
  if (item.kind === "STAGES") return <StageReviewCard item={item} onDecide={(action, words, placement) => handlers.decide(item, action, words, placement)} />;
  if (item.kind === "STRUCTURE") return <StructureReviewCard item={item} onDecide={(action, words) => handlers.decide(item, action, words)} />;
  if (item.kind === "READINGS") return <ReadingReviewCard item={item} onDecide={(action, words) => handlers.decide(item, action, words)} />;
  if (item.kind === "LAYERS") return <LayerReviewCard item={item} onDecide={(action, words) => handlers.decide(item, action, words)} />;
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
