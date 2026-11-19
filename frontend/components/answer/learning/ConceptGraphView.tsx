"use client";

import { useId, useState } from "react";
import Link from "next/link";

import { ConceptGraphFigure } from "@/components/answer/learning/ConceptGraphFigure";
import { READING_PROSE } from "@/components/answer/place/figureMarks";
import { CitedText } from "@/components/answer/ProseBlockView";
import { TextLink } from "@/components/ui/TextLink";
import type { CraftLink } from "@/lib/answerShapes";
import { chosenNode, LIST_CRAFTS_START, nodeChoiceLabel, shownCrafts } from "@/lib/conceptGraph";
import type { ConceptGraphBlock, ConceptNode } from "@/lib/explainerLearning";

function ConceptChoice({ nodes, current, onChoose }: { nodes: readonly ConceptNode[]; current: string; onChoose: (termKey: string) => void }) {
  return (
    <div role="group" aria-label="Shared concept" className="flex min-w-0 flex-wrap gap-2" data-testid="concept-choice">
      {nodes.map((node) => (
        <button key={node.termKey} type="button" aria-pressed={node.termKey === current} onClick={() => onChoose(node.termKey)} className="kv-chip max-w-full whitespace-normal text-start">
          {nodeChoiceLabel(node)}
        </button>
      ))}
    </div>
  );
}

function CraftList({ node, focus, all, onShowAll }: { node: ConceptNode; focus: CraftLink | null; all: boolean; onShowAll: () => void }) {
  const crafts = shownCrafts(node, all);
  const listId = useId();
  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3">
      <ul id={listId} className="grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-ink-1 md:grid-cols-[repeat(2,minmax(0,1fr))] md:gap-x-8" aria-label={`Crafts that share ${node.label}`} data-testid="concept-list">
        {crafts.map((entry) => (
          <li key={entry.craft.slug} className="grid min-w-0 content-start gap-1 border-b border-rule py-3" data-testid="concept-list-craft" data-focus={entry.craft.slug === focus?.slug ? "true" : "false"}>
            <Link href={entry.craft.path} className="kv-link w-fit break-words font-ui text-h4">
              {entry.craft.name}
            </Link>
            <CitedText id={entry.sentence.id} sentences={[entry.sentence]} className={READING_PROSE} />
          </li>
        ))}
      </ul>
      {!all && node.crafts.length > LIST_CRAFTS_START ? (
        <p data-testid="concept-show-all">
          <TextLink onClick={onShowAll} expanded={false} controls={listId} standalone>
            Show all {node.crafts.length}
          </TextLink>
        </p>
      ) : null}
    </div>
  );
}

export function ConceptGraphView({ focus, nodes, initialTermKey = null }: { focus: CraftLink | null; nodes: readonly ConceptNode[]; reduce?: boolean; initialTermKey?: string | null }) {
  const [termKey, setTermKey] = useState<string | null>(initialTermKey);
  const [all, setAll] = useState(false);
  if (nodes.length === 0) return null;
  const node = chosenNode(nodes, termKey);
  const choose = (key: string) => {
    setTermKey(key);
    setAll(false);
  };
  return (
    <div className="kv-figure grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4" data-testid="concept-graph" data-concept={node.termKey}>
      {nodes.length > 1 ? <ConceptChoice nodes={nodes} current={node.termKey} onChoose={choose} /> : null}
      <ConceptGraphFigure node={node} focus={focus} />
      <CraftList node={node} focus={focus} all={all} onShowAll={() => setAll(true)} />
    </div>
  );
}

export function ConceptGraphBlockView({ block }: { block: ConceptGraphBlock }) {
  return <ConceptGraphView focus={block.focus} nodes={block.nodes} />;
}
