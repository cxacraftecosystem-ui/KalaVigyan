import type { ReactNode } from "react";

import { BundleView, SlotRoot } from "@/components/monograph/BundleView";
import { SERVER_VIEWS } from "@/components/monograph/serverViews";
import { SLOT_CLASS } from "@/components/monograph/slotClass";
import type { MonographSources } from "@/lib/monographRender";
import { nodeElements } from "@/lib/monographRenderElements";
import type { ComponentBundle } from "@/lib/monographRenderLayout";

export type BundleSet = { bundles: Readonly<Record<string, ComponentBundle>>; sources: MonographSources; bare: boolean };

export function serverDrawn(bundles: Readonly<Record<string, ComponentBundle>>, label: string): boolean {
  const bundle = bundles[label];
  return Boolean(bundle?.spec && SERVER_VIEWS[bundle.component.kind]);
}

function unitOf(bundle: ComponentBundle, ref: string, sources: MonographSources): ReactNode {
  const unit = bundle.units[ref];
  if (!unit) throw new Error(`Component ${bundle.component.label} has no unit ${ref}`);
  return nodeElements(unit.nodes, sources);
}

export function DrawnBundle({ label, set }: { label: string; set: BundleSet }) {
  if (serverDrawn(set.bundles, label)) return <ServerBundle label={label} set={set} />;
  return (
    <SlotRoot sources={set.sources} bundles={set.bundles} bare={set.bare}>
      <BundleView label={label} />
    </SlotRoot>
  );
}

export function ServerBundle({ label, set }: { label: string; set: BundleSet }) {
  const bundle = set.bundles[label];
  const View = bundle?.spec ? SERVER_VIEWS[bundle.component.kind] : undefined;
  if (!bundle?.spec || !View) return null;
  const view = (
    <View
      component={bundle.component}
      spec={bundle.spec}
      unitRefs={Object.keys(bundle.units)}
      renderUnit={(ref) => unitOf(bundle, ref, set.sources)}
      renderComponent={(nested) => <DrawnBundle key={nested} label={nested} set={set} />}
    />
  );
  if (set.bare) return view;
  return (
    <div className={SLOT_CLASS} data-component={label} data-kind={bundle.component.kind}>
      {view}
    </div>
  );
}
