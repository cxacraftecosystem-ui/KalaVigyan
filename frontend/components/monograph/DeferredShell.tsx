"use client";

import { useEffect } from "react";

import { BundleView, SlotRoot } from "@/components/monograph/BundleView";
import { DataScript } from "@/components/monograph/DataScript";
import { announce, SHELL_COMPLETE_EVENT } from "@/components/monograph/kitGate";
import { shellNodes } from "@/components/monograph/ShellTree";
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
      <div hidden>
        {part.data.map((block) => (
          <DataScript key={block.id} id={block.id} value={block.value} />
        ))}
      </div>
    </SlotRoot>
  );
}
