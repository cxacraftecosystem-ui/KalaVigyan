"use client";

import { ChemEquation } from "@/components/answer/ChemEquation";
import { SourceChip } from "@/components/answer/matter/SourceChip";
import type { Molecule3dBlock } from "@/lib/explainerMatter";

export function MoleculeCaption({ block }: { block: Molecule3dBlock }) {
  return (
    <figcaption className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1" data-testid="molecule-caption">
      <span className="break-words font-reading text-h3 text-ink-1">
        {block.name}
        <SourceChip sourceId={block.sourceId} />
      </span>
      {block.formula ? <ChemEquation equation={block.formula} display={false} label={block.formula} className="text-body" /> : null}
      <span className="font-code text-label text-ink-3">PubChem CID {block.pubchemCid}</span>
    </figcaption>
  );
}
