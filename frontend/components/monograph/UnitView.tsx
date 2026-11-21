import { createElement, type ReactNode } from "react";

import { unitLanguage } from "@/lib/documentLanguages";
import type { MonographNode, MonographUnit } from "@/lib/monographDocument";
import type { MonographSources } from "@/lib/monographRender";
import { nodeElements } from "@/lib/monographRenderElements";

const BLOCK_TAGS = new Set(["p", "h2", "h3", "h4", "li", "dt", "dd", "blockquote", "figcaption", "span", "div", "strong", "small", "td", "th"]);

export type UnitViewProps = { unit: MonographUnit; sources: MonographSources; as?: string; className?: string; id?: string };

function checkedTag(tag: string): string {
  if (!BLOCK_TAGS.has(tag)) throw new Error(`A unit is not drawn as <${tag}>`);
  return tag;
}

export function UnitView({ unit, sources, as, className, id }: UnitViewProps) {
  return createElement(checkedTag(as ?? unit.tag), { className, id, ...unitLanguage(unit) }, nodeElements(unit.nodes, sources));
}

export function unitNodes(unit: MonographUnit, sources: MonographSources): ReactNode {
  const language = unitLanguage(unit);
  const drawn = nodeElements(unit.nodes, sources);
  return language.lang ? createElement("span", language, drawn) : drawn;
}

export type NodesViewProps ={ nodes: readonly MonographNode[]; sources: MonographSources; as?: string; className?: string };

export function NodesView({ nodes, sources, as = "span", className }: NodesViewProps) {
  return createElement(checkedTag(as), { className }, nodeElements(nodes, sources));
}
