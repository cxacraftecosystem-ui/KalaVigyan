import { BundleView, SlotRoot } from "@/components/monograph/BundleView";
import { shellNodes } from "@/components/monograph/ShellTree";
import type { MonographDocument } from "@/lib/monographDocument";
import { bundleSources } from "@/lib/monographRenderKit";
import { componentBundles } from "@/lib/monographRenderLayout";
import { shellTree } from "@/lib/monographShellTree";

import "./authoredShell.css";

const SHELL_ID = "kv-main";

export function AuthoredShell({ document, shell }: { document: MonographDocument; shell: string }) {
  const natives = Object.keys(document.specs);
  const bundles = Object.assign({}, ...natives.map((label) => componentBundles(document, label)));
  const tree = shellTree(shell, new Set(natives));
  return (
    <SlotRoot sources={bundleSources(document, bundles)} bundles={bundles} bare>
      <div id={SHELL_ID}>{shellNodes(tree, (label) => <BundleView label={label} />)}</div>
    </SlotRoot>
  );
}
