"use client";

import Link from "next/link";

import type { CraftLink } from "@/lib/answerShapes";
import { graphLayout, graphSummary, type GraphPoint } from "@/lib/conceptGraph";
import type { ConceptNode } from "@/lib/explainerLearning";
import { cn } from "@/lib/utils";

const NODE = "kv-chip max-w-full justify-center whitespace-normal px-2.5 py-1 text-center leading-tight";
const CROWDED = 5;

function placed(at: GraphPoint) {
  return { left: `${at.x}%`, top: `${at.y}%` };
}

function Spokes({ points }: { points: GraphPoint[] }) {
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full" aria-hidden>
      {points.map((point) => (
        <line key={`${point.x}-${point.y}`} x1={50} y1={50} x2={point.x} y2={point.y} vectorEffect="non-scaling-stroke" strokeWidth={1} stroke="var(--rule-strong)" data-testid="concept-spoke" />
      ))}
    </svg>
  );
}

export function ConceptGraphFigure({ node, focus }: { node: ConceptNode; focus: CraftLink | null; reduce?: boolean }) {
  const layout = graphLayout(node, focus);
  const points = [...layout.crafts.map((craft) => craft.at), ...(layout.more ? [layout.more.at] : [])];
  return (
    <figure className="m-0 min-w-0" data-testid="concept-figure">
      <div role="img" aria-label={graphSummary(node)} className={cn("relative w-full min-w-0 overflow-hidden rounded-plate bg-sunk [forced-color-adjust:none] sm:aspect-[5/2]", points.length > CROWDED ? "aspect-square" : "aspect-[4/3]")}>
        <Spokes points={points} />
        <div aria-hidden className="absolute inset-0">
          <span className="absolute flex w-[34%] -translate-x-1/2 -translate-y-1/2 justify-center" style={placed({ x: 50, y: 50 })}>
            <span className="inline-flex max-w-full items-center justify-center rounded-plate bg-ink-1 px-3 py-1.5 text-center font-ui text-ui font-semibold leading-tight text-ground" data-testid="concept-hub">
              {node.label}
            </span>
          </span>
          {layout.crafts.map((craft) => (
            <span key={craft.entry.craft.slug} className="absolute flex w-[28%] -translate-x-1/2 -translate-y-1/2 justify-center" style={placed(craft.at)}>
              <Link href={craft.entry.craft.path} tabIndex={-1} className={cn(NODE, "bg-raised", craft.focus ? "border-ink-1 font-semibold text-ink-1" : null)} data-testid="concept-craft-node" data-focus={craft.focus ? "true" : "false"}>
                {craft.entry.craft.name}
              </Link>
            </span>
          ))}
          {layout.more ? (
            <span className="absolute flex w-[28%] -translate-x-1/2 -translate-y-1/2 justify-center" style={placed(layout.more.at)}>
              <span className="inline-flex items-center rounded-pill border border-dashed border-rule-strong bg-raised px-2.5 py-1 font-ui text-label text-ink-3 [font-variant-numeric:lining-nums_tabular-nums]" data-testid="concept-more">
                +{layout.more.count}
              </span>
            </span>
          ) : null}
        </div>
      </div>
    </figure>
  );
}
