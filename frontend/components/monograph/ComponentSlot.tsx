import { NestedSlots, SlotRoot } from "@/components/monograph/BundleView";
import { ComponentHome } from "@/components/monograph/ComponentHome";
import { COMPONENT_VIEWS } from "@/components/monograph/componentViews";
import { DrawnBundle } from "@/components/monograph/ServerBundle";
import { SLOT_CLASS } from "@/components/monograph/slotClass";
import type { MonographComponent, MonographDocument } from "@/lib/monographDocument";
import { bundleSources } from "@/lib/monographRenderKit";
import { componentBundles, placedComponents, slotId, specStrings } from "@/lib/monographRenderLayout";
import { APP_KINDS, componentHome } from "@/lib/monographScopes";

export type SlotDrawing = "view" | "fragment" | "none";

const UNIT_REF = /^u\d{4,}$/;

export function unitsHeld(document: MonographDocument, label: string): boolean {
  return Object.values(componentBundles(document, label)).every((bundle) => specStrings(bundle.spec).every((value) => !UNIT_REF.test(value) || Object.hasOwn(document.content.units, value)));
}

export function slotDrawing(document: MonographDocument, label: string): SlotDrawing {
  const component = document.content.components.find((found) => found.label === label);
  if (!component) return "none";
  if (Object.hasOwn(document.specs, label) && COMPONENT_VIEWS[component.kind] && unitsHeld(document, label)) return "view";
  if (Object.hasOwn(document.fragments, label)) return "fragment";
  return "none";
}

type SlotProps = { document: MonographDocument; label: string; scoped?: boolean };

function homeOf(document: MonographDocument, component: MonographComponent) {
  const spec = Object.hasOwn(document.specs, component.label) ? document.specs[component.label] : null;
  return componentHome(component.label, component.kind, spec);
}

function ViewSlot({ document, component, scoped }: { document: MonographDocument; component: MonographComponent; scoped: boolean }) {
  const bundles = componentBundles(document, component.label);
  const view = <DrawnBundle label={component.label} set={{ bundles, sources: bundleSources(document, bundles), bare: !APP_KINDS.has(component.kind) }} />;
  if (!scoped) return view;
  return (
    <ComponentHome home={homeOf(document, component)} label={component.label} kind={component.kind}>
      {view}
    </ComponentHome>
  );
}

function FragmentSlot({ document, component, scoped }: { document: MonographDocument; component: MonographComponent; scoped: boolean }) {
  const label = component.label;
  const nested = placedComponents(document, label);
  const bundles = Object.assign({}, ...nested.map((found) => componentBundles(document, found)));
  const html = document.fragments[label];
  return (
    <>
      {scoped ? (
        <ComponentHome home={homeOf(document, component)} label={label} kind={component.kind} fragment={{ id: slotId(label), html }} />
      ) : (
        <div className={SLOT_CLASS} id={slotId(label)} data-component={label} dangerouslySetInnerHTML={{ __html: html }} />
      )}
      {nested.length ? (
        <SlotRoot sources={bundleSources(document, bundles)} bundles={bundles} bare>
          <NestedSlots hostId={slotId(label)} />
        </SlotRoot>
      ) : null}
    </>
  );
}

export function ComponentSlot({ document, label, scoped = true }: SlotProps) {
  const drawing = slotDrawing(document, label);
  const component = document.content.components.find((found) => found.label === label);
  if (drawing === "none" || !component) return null;
  if (drawing === "view") return <ViewSlot document={document} component={component} scoped={scoped} />;
  return <FragmentSlot document={document} component={component} scoped={scoped} />;
}
