"use client";

import { hasRenderer, renderBlock } from "@/components/answer/blockRenderers";
import { useAuth } from "@/components/AuthProvider";
import { blockAnchor } from "@/lib/answerEssay";
import type { ReuseMarker } from "@/lib/explainerBlockBase";
import { reusedLabel, type TypedBlock } from "@/lib/explainerView";
import { canHideGenerated } from "@/lib/permissions";
import { hiddenFrom } from "@/lib/simulationView";

function ReuseNote({ reuse }: { reuse: ReuseMarker }) {
  return (
    <p className="mb-2 font-ui text-caption text-ink-3" data-testid="reuse-marker">
      {reusedLabel(reuse.storedAt)}
    </p>
  );
}

function BlockFrame({ block }: { block: TypedBlock }) {
  return (
    <div id={blockAnchor(block.id)} className="min-w-0" data-testid="explainer-block" data-kind={block.kind} data-block-id={block.id}>
      {block.reuse ? <ReuseNote reuse={block.reuse} /> : null}
      {renderBlock(block)}
    </div>
  );
}

function HiddenBlockFrame({ block }: { block: TypedBlock }) {
  const canHide = canHideGenerated(useAuth().user);
  return hiddenFrom(block, canHide) ? null : <BlockFrame block={block} />;
}

export function ExplainerBlockView({ block }: { block: TypedBlock; reduce?: boolean }) {
  if (!hasRenderer(block)) return null;
  if (hiddenFrom(block, false)) return <HiddenBlockFrame block={block} />;
  return <BlockFrame block={block} />;
}
