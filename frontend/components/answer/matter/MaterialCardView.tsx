"use client";

import type { ReactNode } from "react";
import { TriangleAlert } from "lucide-react";

import { ChemEquation } from "@/components/answer/ChemEquation";
import { SourceChip } from "@/components/answer/matter/SourceChip";
import { CitedText } from "@/components/answer/ProseBlockView";
import type { MaterialCardBlock } from "@/lib/explainerMatter";
import { materialRoleText, pubchemHref } from "@/lib/processView";
import { wikidataUrl } from "@/lib/supplyView";

function Outbound({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="kv-link w-fit font-ui text-caption">
      {children}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid min-w-0 content-start gap-1 border-b border-rule py-3" data-testid="material-tile">
      <dt className="font-ui text-label text-ink-3">{label}</dt>
      <dd className="grid min-w-0 gap-1">{children}</dd>
    </div>
  );
}

function CompoundRecord({ block }: { block: MaterialCardBlock }) {
  if (!block.sourceId) {
    const pubchem = pubchemHref(block.pubchemCid);
    return pubchem ? <Outbound href={pubchem}>PubChem</Outbound> : null;
  }
  return (
    <span className="font-code text-label text-ink-3" data-testid="material-record">
      {block.pubchemCid === null ? null : `PubChem CID ${block.pubchemCid}`}
      {block.formula ? null : <SourceChip sourceId={block.sourceId} />}
    </span>
  );
}

function CompoundFact({ block }: { block: MaterialCardBlock }) {
  return (
    <Fact label={block.formula ? "Formula" : "Compound"}>
      {block.formula ? (
        <span className="min-w-0 break-words" data-testid="material-formula">
          <ChemEquation equation={block.formula} display={false} label={block.formula} className="text-body" />
          {block.sourceId ? <SourceChip sourceId={block.sourceId} /> : null}
        </span>
      ) : null}
      <CompoundRecord block={block} />
    </Fact>
  );
}

function MaterialFacts({ block }: { block: MaterialCardBlock }) {
  const role = materialRoleText(block.role, block.materialKind);
  const compound = Boolean(block.formula || block.sourceId);
  if (!compound && !role) return null;
  return (
    <dl className="grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-ink-1 sm:grid-cols-[repeat(2,minmax(0,1fr))] sm:gap-x-8">
      {compound ? <CompoundFact block={block} /> : null}
      {role ? (
        <Fact label="Role">
          <span className="font-ui text-ui-lg text-ink-1">{role}</span>
        </Fact>
      ) : null}
    </dl>
  );
}

function Handling({ block }: { block: MaterialCardBlock }) {
  if (block.handling.length === 0) return null;
  return (
    <div className="grid min-w-0 gap-1.5 border-s-2 border-madder bg-madder-wash px-4 py-3" data-testid="material-handling">
      <p className="inline-flex items-center gap-1.5 font-ui text-label font-semibold text-madder">
        <TriangleAlert className="h-4 w-4 shrink-0" aria-hidden />
        Handling
      </p>
      <CitedText id={`${block.id}-handling`} sentences={block.handling} className="max-w-measure font-reading text-body-sm text-ink-1" />
    </div>
  );
}

function LocalNames({ block }: { block: MaterialCardBlock }) {
  if (block.localNames.length === 0 && !block.wikidataId) return null;
  return (
    <p className="mt-1 flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-0.5 font-ui text-ui font-normal text-ink-2" data-testid="material-local-names">
      {block.localNames.length > 0 ? (
        <span className="min-w-0 break-words font-reading italic">
          <span className="sr-only">Local names: </span>
          {block.localNames.join(" · ")}
        </span>
      ) : null}
      {block.wikidataId ? <Outbound href={wikidataUrl(block.wikidataId)}>Wikidata</Outbound> : null}
    </p>
  );
}

export function MaterialCardView({ block }: { block: MaterialCardBlock }) {
  return (
    <article className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4" data-testid="material-card">
      <header className="min-w-0">
        <h3 className="break-words font-reading text-h3 text-ink-1">{block.name}</h3>
        <LocalNames block={block} />
      </header>
      <MaterialFacts block={block} />
      <CitedText id={`${block.id}-facts`} sentences={block.facts} className="max-w-measure font-reading text-body text-ink-1" />
      <Handling block={block} />
    </article>
  );
}
