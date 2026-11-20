"use client";

import { useEffect } from "react";

import { BundleView, SlotRoot } from "@/components/monograph/BundleView";
import { DataScript } from "@/components/monograph/DataScript";
import { announce, SHELL_COMPLETE_EVENT } from "@/components/monograph/kitGate";
import { shellNodes } from "@/components/monograph/ShellTree";
import type { KitDataBlock } from "@/lib/monographRenderKit";
import type { ShellRest } from "@/lib/monographRenderShell";

function settled(then: () => void): () => void {
  let second = 0;
  const first = requestAnimationFrame(() => {
    second = requestAnimationFrame(then);
  });
  return () => {
    cancelAnimationFrame(first);
    cancelAnimationFrame(second);
  };
}

export function scopedBlocks(blocks: readonly KitDataBlock[]): [string | null, KitDataBlock[]][] {
  const scopes = new Map<string | null, KitDataBlock[]>();
  for (const block of blocks) scopes.set(block.scope, [...(scopes.get(block.scope) ?? []), block]);
  return [...scopes];
}

function KitData({ blocks }: { blocks: readonly KitDataBlock[] }) {
  return (
    <>
      {scopedBlocks(blocks).map(([scope, held]) => (
        <div key={scope ?? "page"} className={scope ? `bx bx-${scope}` : undefined} hidden>
          {held.map((block) => (
            <DataScript key={block.id} id={block.id} value={block.value} />
          ))}
        </div>
      ))}
    </>
  );
}

export function DeferredShell({ part, jump }: { part: ShellRest; jump: string | null }) {
  useEffect(
    () =>
      settled(() => {
        if (jump) document.getElementById(jump)?.scrollIntoView({ block: "start" });
        announce(window, SHELL_COMPLETE_EVENT);
      }),
    [jump]
  );
  return (
    <SlotRoot sources={part.sources} bundles={part.bundles} bare>
      {shellNodes(part.tree, (label) => (
        <BundleView label={label} />
      ))}
      <KitData blocks={part.data} />
    </SlotRoot>
  );
}
