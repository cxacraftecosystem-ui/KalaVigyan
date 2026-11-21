import { isDeclared } from "@/lib/componentSpecsGeneral";
import type { ComponentView, ComponentViewProps, ComponentViews } from "@/lib/componentViewContract";

export function eitherView(authored: ComponentView, declared: ComponentView): ComponentView {
  const Authored = authored;
  const Declared = declared;
  return function EitherView(props: ComponentViewProps) {
    return isDeclared(props.spec) ? <Declared {...props} /> : <Authored {...props} />;
  };
}

export function withDeclared(authored: ComponentViews, declared: ComponentViews): ComponentViews {
  const views: Record<string, ComponentView> = {};
  for (const [kind, view] of Object.entries(authored)) {
    const form = declared[kind];
    if (view) views[kind] = form ? eitherView(view, form) : view;
  }
  return views;
}
