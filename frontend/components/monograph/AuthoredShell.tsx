import { BundleView, SlotRoot } from "@/components/monograph/BundleView";
import { DeferredShellSlot } from "@/components/monograph/DeferredShellSlot";
import { DrawnBundle, type BundleSet } from "@/components/monograph/ServerBundle";
import { shellNodes } from "@/components/monograph/ShellTree";
import type { MonographDocument } from "@/lib/monographDocument";
import { bundleSources } from "@/lib/monographRenderKit";
import { componentBundles } from "@/lib/monographRenderLayout";
import { leadLength, shellPart } from "@/lib/monographRenderShell";
import { shellTree } from "@/lib/monographShellTree";

import "./authoredShell.css";

const SHELL_ID = "kv-main";

export type AuthoredShellProps = { document: MonographDocument; shell: string; rest?: string | null };

function slot(label: string) {
  return <BundleView label={label} />;
}

export function AuthoredShell({ document, shell, rest = null }: AuthoredShellProps) {
  const natives = Object.keys(document.specs);
  const tree = shellTree(shell, new Set(natives));
  if (rest !== null) {
    const lead = shellPart(document, tree.slice(0, leadLength(tree)));
    const set: BundleSet = { bundles: lead.bundles, sources: lead.sources, bare: true };
    return (
      <div id={SHELL_ID}>
        {shellNodes(lead.tree, (label) => (
          <DrawnBundle label={label} set={set} />
        ))}
        <DeferredShellSlot src={rest} version={document.version} />
      </div>
    );
  }
  const bundles = Object.assign({}, ...natives.map((label) => componentBundles(document, label)));
  return (
    <SlotRoot sources={bundleSources(document, bundles)} bundles={bundles} bare>
      <div id={SHELL_ID}>{shellNodes(tree, slot)}</div>
    </SlotRoot>
  );
}
