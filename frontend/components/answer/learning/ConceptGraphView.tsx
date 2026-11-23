"use client";

import { useId, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";

import { CitationProvider, useOptionalCitations, type CitationLookup } from "@/components/answer/CitationContext";
import { ConceptGraphFigure } from "@/components/answer/learning/ConceptGraphFigure";
import { useConceptCrafts, type ConceptCraftsView } from "@/components/answer/learning/useConceptCrafts";
import { READING_PROSE } from "@/components/answer/place/figureMarks";
import { CitedText } from "@/components/answer/ProseBlockView";
import { TextLink } from "@/components/ui/TextLink";
import type { CraftLink } from "@/lib/answerShapes";
import { listedSourceNumbers } from "@/lib/citations";
import { chosenNode, nodeChoiceLabel } from "@/lib/conceptGraph";
import type { ConceptGraphBlock, ConceptNode } from "@/lib/explainerLearning";
import type { SourceRef } from "@/lib/types";

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

function PagedCitations({ sources, children }: { sources: readonly SourceRef[]; children: ReactNode }) {
  const outer = useOptionalCitations();
  const lookup = useMemo<CitationLookup | null>(() => {
    if (!outer || sources.length === 0) return outer;
    return { numbers: listedSourceNumbers(sources, outer.numbers), sourcesById: new Map([...outer.sourcesById, ...sources.map((source) => [source.id, source] as const)]) };
  }, [outer, sources]);
  return lookup ? <CitationProvider value={lookup}>{children}</CitationProvider> : <>{children}</>;
}

function listStatus(crafts: ConceptCraftsView): string {
  if (crafts.phase === "reading") return `Reading all ${crafts.total} crafts.`;
  if (crafts.phase === "failed") return `The crafts could not be read. Press Show all ${crafts.total} to try again.`;
  return "";
}

function CraftList({ node, focus }: { node: ConceptNode; focus: CraftLink | null }) {
  const crafts = useConceptCrafts(node, focus?.slug ?? null);
  const listId = useId();
  return (
    <PagedCitations sources={crafts.sources}>
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3">
        <ul id={listId} className="grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-ink-1 md:grid-cols-[repeat(2,minmax(0,1fr))] md:gap-x-8" aria-label={`Crafts that share ${node.label}`} data-testid="concept-list">
          {crafts.shown.map((entry) => (
            <li key={entry.craft.slug} className="grid min-w-0 content-start gap-1 border-b border-rule py-3" data-testid="concept-list-craft" data-focus={entry.craft.slug === focus?.slug ? "true" : "false"}>
              <Link href={entry.craft.path} className="kv-link w-fit break-words font-ui text-h4">
                {entry.craft.name}
              </Link>
              <CitedText id={entry.sentence.id} sentences={[entry.sentence]} className={READING_PROSE} />
            </li>
          ))}
        </ul>
        {!crafts.all && crafts.expandable ? (
          <div className="grid gap-1" data-testid="concept-show-all">
            <p>
              <TextLink onClick={crafts.showAll} expanded={false} controls={listId} standalone>
                Show all {crafts.total}
              </TextLink>
            </p>
            <p role="status" className="font-ui text-label text-ink-2">
              {listStatus(crafts)}
            </p>
          </div>
        ) : null}
      </div>
    </PagedCitations>
  );
}

export function ConceptGraphView({ focus, nodes, initialTermKey = null }: { focus: CraftLink | null; nodes: readonly ConceptNode[]; reduce?: boolean; initialTermKey?: string | null }) {
  const [termKey, setTermKey] = useState<string | null>(initialTermKey);
  if (nodes.length === 0) return null;
  const node = chosenNode(nodes, termKey);
  return (
    <div className="kv-figure grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4" data-testid="concept-graph" data-concept={node.termKey}>
      {nodes.length > 1 ? <ConceptChoice nodes={nodes} current={node.termKey} onChoose={setTermKey} /> : null}
      <ConceptGraphFigure node={node} focus={focus} />
      <CraftList key={node.termKey} node={node} focus={focus} />
    </div>
  );
}

export function ConceptGraphBlockView({ block }: { block: ConceptGraphBlock }) {
  return <ConceptGraphView focus={block.focus} nodes={block.nodes} />;
}
