"use client";

import { useState } from "react";
import { AlertCircle, Code2, Eye, EyeOff } from "lucide-react";

import { useAnswerId } from "@/components/answer/AnswerContext";
import { GeneratedCode } from "@/components/answer/play/GeneratedCode";
import { GeneratedSources } from "@/components/answer/play/GeneratedSources";
import { SandboxFrame } from "@/components/answer/play/SandboxFrame";
import { useSimulationHiding, type HidingControls } from "@/components/answer/play/useSimulationHiding";
import { useAuth } from "@/components/AuthProvider";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import type { SimulationBlock } from "@/lib/explainerPlay";
import { canHideGenerated } from "@/lib/permissions";
import { generatedCaption, keptAsPiece, valueBases } from "@/lib/simulationView";

const FIGURE = "kv-figure m-0 grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4";
const ICON = "h-4 w-4";

function Caption({ block }: { block: SimulationBlock }) {
  return (
    <p className="min-w-0 break-words font-ui text-caption text-ink-3 [font-variant-numeric:lining-nums]" data-testid="generated-caption">
      {generatedCaption(block)}
    </p>
  );
}

function HidingFailed({ hiding }: { hiding: HidingControls | null }) {
  if (!hiding?.failed) return null;
  return (
    <p role="alert" className="flex items-center gap-1.5 font-ui text-ui font-normal text-error" data-testid="generated-hiding-failed">
      <AlertCircle className={ICON} aria-hidden />
      The change was not saved. Try again.
    </p>
  );
}

function HiddenExplainer({ block, hiding }: { block: SimulationBlock; hiding: HidingControls | null }) {
  return (
    <figure className={FIGURE} data-testid="generated-explainer" data-hidden="true" lang="en">
      <Caption block={block} />
      <p className="flex min-w-0 items-center gap-2 font-ui text-ui font-normal text-ink-2">
        <EyeOff className={`${ICON} shrink-0 text-ink-3`} aria-hidden />
        <span className="min-w-0 break-words">Hidden · {block.title}</span>
      </p>
      {hiding ? (
        <ActionGroup align="start">
          <Button variant="quiet" size="sm" disabled={hiding.busy} onClick={() => hiding.change(false)} data-testid="generated-show">
            <Eye className={ICON} aria-hidden />
            Show again
          </Button>
        </ActionGroup>
      ) : null}
      <HidingFailed hiding={hiding} />
    </figure>
  );
}

function ExplainerActions({ block, code, onCode, hiding }: { block: SimulationBlock; code: boolean; onCode: () => void; hiding: HidingControls | null }) {
  return (
    <ActionGroup align="start">
      <Button variant="quiet" size="sm" aria-expanded={code} aria-controls={code ? `${block.id}-code` : undefined} onClick={onCode} data-testid="generated-view-code">
        <Code2 className={ICON} aria-hidden />
        {code ? "Close code" : "View code"}
      </Button>
      {hiding ? (
        <Button variant="quiet" size="sm" disabled={hiding.busy} onClick={() => hiding.change(true)} data-testid="generated-hide">
          <EyeOff className={ICON} aria-hidden />
          Hide explainer
        </Button>
      ) : null}
    </ActionGroup>
  );
}

export function GeneratedExplainerView({ block, canHide, hiding }: { block: SimulationBlock; canHide: boolean; hiding: HidingControls | null }) {
  const [code, setCode] = useState(false);
  const bases = valueBases(block);
  if (bases === null) return null;
  if (hiding?.hidden ?? block.hidden) return canHide ? <HiddenExplainer block={block} hiding={hiding} /> : null;
  const titleId = `${block.id}-title`;
  return (
    <figure className={FIGURE} aria-labelledby={titleId} data-testid="generated-explainer" data-hidden="false" lang="en">
      <header className="grid min-w-0 gap-1">
        <Caption block={block} />
        <h3 id={titleId} className="break-words font-reading text-h3 text-ink-1">
          {block.title}
        </h3>
      </header>
      <SandboxFrame block={block} />
      <GeneratedSources values={block.values} bases={bases} grounds={block.grounds ?? []} reactions={block.reactions ?? []} />
      <ExplainerActions block={block} code={code} onCode={() => setCode((open) => !open)} hiding={hiding} />
      {code ? <GeneratedCode id={`${block.id}-code`} html={block.html} /> : null}
      <HidingFailed hiding={hiding} />
    </figure>
  );
}

export function GeneratedExplainer({ block }: { block: SimulationBlock }) {
  const canHide = canHideGenerated(useAuth().user) && keptAsPiece(block);
  const answerId = useAnswerId();
  const hiding = useSimulationHiding(canHide ? answerId : null, block.id, block.hidden);
  return <GeneratedExplainerView block={block} canHide={canHide} hiding={hiding} />;
}
