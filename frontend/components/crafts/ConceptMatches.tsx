"use client";

import Link from "next/link";
import { useCallback, useId, useMemo, useState } from "react";

import { Cite } from "@/components/editorial/CitationCluster";
import { useRemote } from "@/components/hooks/useRemote";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/Chip";
import { craftHref } from "@/lib/atlasCollection";
import { conceptNeighbours } from "@/lib/atlasIndex";
import { conceptDek, conceptRows, conceptTerms, craftMeta, fetchSharedConcept, isTermKey, markTerms, RESULT_ROWS_SHOWN, type ConceptRow, type MarkedPart } from "@/lib/atlasSearch";
import { nodeCraftCount } from "@/lib/conceptGraph";
import type { ConceptHit } from "@/lib/craftCatalogue";
import type { CraftCatalogue } from "@/lib/craftCatalogueContract";
import type { SourceRef } from "@/lib/types";

type Lookup = { numbers: ReadonlyMap<string, number>; sourcesById: ReadonlyMap<string, SourceRef> };

const WORD_GOES_ON = /^[\p{L}\p{N}]/u;
const PLURAL_END = /^e?s(?![\p{L}\p{N}])/u;

export function wholeWordMarks(parts: readonly MarkedPart[]): MarkedPart[] {
  return parts.map((part, at) => {
    const next = parts[at + 1]?.text ?? "";
    if (!part.mark || !WORD_GOES_ON.test(next) || PLURAL_END.test(next)) return part;
    return { ...part, mark: false };
  });
}

function CitedLine({ row, terms, lookup }: { row: ConceptRow; terms: readonly string[]; lookup: Lookup }) {
  if (!row.cited) return null;
  const sentence = row.cited.sentence;
  return (
    <p className="mt-1 font-reading text-body-sm text-ink-2">
      <span data-cite-host="">
        {wholeWordMarks(markTerms(sentence.text, terms)).map((part, at) =>
          part.mark ? (
            <mark key={at} className="bg-turmeric-wash px-px text-inherit">
              {part.text}
            </mark>
          ) : (
            <span key={at}>{part.text}</span>
          )
        )}
        <Cite citations={sentence.citations} numbers={lookup.numbers} sourcesById={lookup.sourcesById} />
      </span>
    </p>
  );
}

function ResultRow({ row, catalogue, terms, lookup }: { row: ConceptRow; catalogue: CraftCatalogue; terms: readonly string[]; lookup: Lookup }) {
  return (
    <li className="grid min-w-0 content-start gap-0.5 border-t border-rule py-3.5" data-testid="concept-row">
      <Link href={craftHref(row.craft)} className="w-fit font-reading text-body font-medium text-ink-1 hover:text-indigo hover:underline hover:underline-offset-3">
        {row.craft.displayName}
      </Link>
      <span className="font-ui text-label font-normal text-ink-3">{craftMeta(catalogue, row.craft)}</span>
      <CitedLine row={row} terms={terms} lookup={lookup} />
    </li>
  );
}

function lookupOf(sources: readonly SourceRef[]): Lookup {
  return { numbers: new Map(sources.map((source, at) => [source.id, at + 1])), sourcesById: new Map(sources.map((source) => [source.id, source])) };
}

function Neighbours({ hit, catalogue, onQuery }: { hit: ConceptHit; catalogue: CraftCatalogue; onQuery: (query: string) => void }) {
  const neighbours = conceptNeighbours(catalogue, hit.concept);
  if (!neighbours.length) return null;
  return (
    <p className="mt-3 flex flex-wrap items-center gap-2">
      <span className="me-1 font-ui text-label font-normal text-ink-3">Linked to the same crafts</span>
      {neighbours.map((found) => (
        <Chip key={found.concept.key} count={found.shared} onClick={() => onQuery(found.concept.label.toLowerCase())}>
          {found.concept.label.toLowerCase()}
        </Chip>
      ))}
    </p>
  );
}

export function ConceptGroup({ hit, catalogue, onQuery }: { hit: ConceptHit; catalogue: CraftCatalogue; onQuery: (query: string) => void }) {
  const key = hit.concept.key;
  const load = useCallback(() => fetchSharedConcept(key), [key]);
  const shared = useRemote(isTermKey(key) ? load : null);
  const [open, setOpen] = useState(false);
  const listId = useId();
  const rows = useMemo(() => conceptRows(hit.crafts, shared.data), [hit.crafts, shared.data]);
  const lookup = useMemo(() => lookupOf(shared.data?.sources ?? []), [shared.data]);
  const terms = conceptTerms(hit.concept);
  const shown = open ? rows : rows.slice(0, RESULT_ROWS_SHOWN);
  return (
    <div className="pt-[22px] pb-2" data-testid="concept-match">
      <h3 className="font-reading text-h3 text-ink-1">{hit.concept.label}</h3>
      <p className="mt-1.5 font-ui text-ui font-normal text-ink-2">{conceptDek(rows, shared.data ? nodeCraftCount(shared.data.node) : 0)}</p>
      <Neighbours hit={hit} catalogue={catalogue} onQuery={onQuery} />
      <ol id={listId} className="mt-4 grid grid-cols-1 md:grid-cols-2 md:gap-x-12">
        {shown.map((row) => (
          <ResultRow key={row.craft.id} row={row} catalogue={catalogue} terms={terms} lookup={lookup} />
        ))}
      </ol>
      {rows.length > RESULT_ROWS_SHOWN ? (
        <ActionGroup className="mt-[18px]">
          <Button variant="quiet" size="sm" aria-expanded={open} aria-controls={listId} onClick={() => setOpen((value) => !value)}>
            {open ? "Show fewer" : `Show all ${rows.length}`}
          </Button>
        </ActionGroup>
      ) : null}
    </div>
  );
}

export function CraftMatches({ crafts, catalogue }: { crafts: readonly ConceptRow["craft"][]; catalogue: CraftCatalogue }) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  const lookup = useMemo(() => lookupOf([]), []);
  if (!crafts.length) return null;
  const rows = crafts.map((craft) => ({ craft, cited: null }));
  const shown = open ? rows : rows.slice(0, RESULT_ROWS_SHOWN * 2);
  return (
    <div className="pt-[22px] pb-2" data-testid="craft-matches">
      <h3 className="font-reading text-h3 text-ink-1">Crafts</h3>
      <ol id={listId} className="mt-4 grid grid-cols-1 md:grid-cols-2 md:gap-x-12">
        {shown.map((row) => (
          <ResultRow key={row.craft.id} row={row} catalogue={catalogue} terms={[]} lookup={lookup} />
        ))}
      </ol>
      {rows.length > shown.length || open ? (
        <ActionGroup className="mt-[18px]">
          <Button variant="quiet" size="sm" aria-expanded={open} aria-controls={listId} onClick={() => setOpen((value) => !value)}>
            {open ? "Show fewer" : `Show all ${rows.length}`}
          </Button>
        </ActionGroup>
      ) : null}
    </div>
  );
}
