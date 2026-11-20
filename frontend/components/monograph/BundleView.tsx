"use client";

import { memo, useEffect, useMemo, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { COMPONENT_VIEWS } from "@/components/monograph/componentViews";
import { MonographSlotProvider, useMonographSlot, type MonographSlotValue } from "@/components/monograph/MonographSlotContext";
import { NestedComponents } from "@/components/monograph/NestedComponents";
import type { MonographSources } from "@/lib/monographRender";
import { nodeElements } from "@/lib/monographRenderElements";
import { fragmentSlots, slotId, type ComponentBundle } from "@/lib/monographRenderLayout";

export const SLOT_CLASS = "kv-slot contents";
export const SLOT_ELEMENT = "kv-slot[component]";

export function SlotRoot({ sources, bundles, bare = false, children }: MonographSlotValue & { children: ReactNode }) {
  const value = useMemo(() => ({ sources, bundles, bare }), [sources, bundles, bare]);
  return <MonographSlotProvider value={value}>{children}</MonographSlotProvider>;
}

export function BundleView({ label }: { label: string }) {
  const { bundles, sources, bare } = useMonographSlot();
  const bundle: ComponentBundle | undefined = bundles[label];
  const renderUnit = useMemo(() => unitRenderer(bundle, sources), [bundle, sources]);
  if (!bundle) return null;
  const View = bundle.spec ? COMPONENT_VIEWS[bundle.component.kind] : undefined;
  if (bundle.spec && View) {
    const view = (
      <NestedComponents.Provider value={renderNested}>
        <View component={bundle.component} spec={bundle.spec} unitRefs={Object.keys(bundle.units)} renderUnit={renderUnit} renderComponent={renderNested} />
      </NestedComponents.Provider>
    );
    if (bare) return view;
    return (
      <div className={SLOT_CLASS} data-component={label} data-kind={bundle.component.kind}>
        {view}
      </div>
    );
  }
  if (bundle.fragment !== null) return <FragmentHtml label={label} html={bundle.fragment} />;
  return null;
}

function renderNested(nested: string): ReactNode {
  return <BundleView key={nested} label={nested} />;
}

function unitRenderer(bundle: ComponentBundle | undefined, sources: MonographSources): (ref: string) => ReactNode {
  return (ref) => {
    const unit = bundle?.units[ref];
    if (!unit) throw new Error(`Component ${bundle?.component.label ?? "?"} has no unit ${ref}`);
    return nodeElements(unit.nodes, sources);
  };
}

export const FragmentHtml = memo(function FragmentHtml({ label, html }: { label: string; html: string }) {
  return (
    <>
      <div className={SLOT_CLASS} id={slotId(label)} data-component={label} dangerouslySetInnerHTML={{ __html: html }} />
      {fragmentSlots(html).length ? <NestedSlots hostId={slotId(label)} /> : null}
    </>
  );
});

type SlotTarget = { label: string; element: Element };

export function NestedSlots({ hostId }: { hostId: string }) {
  const [targets, setTargets] = useState<SlotTarget[]>([]);
  useEffect(() => {
    const host = document.getElementById(hostId);
    if (!host) return;
    setTargets([...host.querySelectorAll(SLOT_ELEMENT)].map((element) => ({ label: element.getAttribute("component") ?? "", element })));
  }, [hostId]);
  return <>{targets.map((target) => createPortal(<BundleView label={target.label} />, target.element, target.label))}</>;
}

export function PlacedComponent({ label }: { label: string }) {
  return <BundleView label={label} />;
}
