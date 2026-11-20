import { readFileSync } from "node:fs";
import { join } from "node:path";

import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { NestingViewProps } from "@/components/monograph/kinds/plates/nesting";
import { componentsHeldBy } from "@/lib/componentSpecsData";
import type { ComponentView, ComponentViews } from "@/lib/componentViewContract";
import type { MonographComponent, MonographContent } from "@/lib/monographDocument";

import { assembledTemplate, PICTURE_DELIVERY } from "./monographMarkup";

const MONOGRAPH = join(__dirname, "..", "..", "backend", "app", "data", "monographs", "Kutch-Ajrakh");
const TOKEN = /<!--[\s\S]*?-->|<(\/?)([a-zA-Z][a-zA-Z0-9:-]*)((?:\s+[^\s"'>/=]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?)*)\s*(\/?)>/g;
const ATTRIBUTE = /([^\s"'>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
const VOID = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"]);
const RAW_TEXT = new Set(["script", "style"]);
const HOISTED_PRELOAD = /<link rel="preload"[^>]*>/g;
const ENTITIES: Readonly<Record<string, string>> = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };
export const ANCHOR_CORRECTIONS: Readonly<Record<string, string>> = { "kutch-ajrakh/policy/gi-registration-card": '[class="label-card gi"]' };

type Tag = { closing: boolean; name: string; attrs: Record<string, string>; start: number; end: number; selfClosing: boolean };

let template: string | null = null;
let content: MonographContent | null = null;

export function approvedTemplate(): string {
  template ??= assembledTemplate();
  return template;
}

export function approvedContent(): MonographContent {
  content ??= JSON.parse(readFileSync(join(MONOGRAPH, "content.json"), "utf8")) as MonographContent;
  return content;
}

export function componentsOfKinds(kinds: readonly string[]): MonographComponent[] {
  return approvedContent().components.filter((component) => kinds.includes(component.kind));
}

export function specOf(label: string): Record<string, unknown> {
  return JSON.parse(readFileSync(join(MONOGRAPH, "specs", `${label.replaceAll("/", "__")}.json`), "utf8")) as Record<string, unknown>;
}

export function unitsWithin(label: string): string[] {
  return approvedContent()
    .layout.filter((entry) => entry.kind === "unit" && entry.within === label)
    .map((entry) => entry.ref);
}

export function decode(text: string): string {
  return text.replace(/&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z]+);/g, (whole, name: string) => {
    if (name.startsWith("#x")) return String.fromCodePoint(parseInt(name.slice(2), 16));
    if (name.startsWith("#")) return String.fromCodePoint(Number(name.slice(1)));
    return ENTITIES[name] ?? whole;
  });
}

function attributesOf(text: string): Record<string, string> {
  const attrs: Record<string, string> = {};
  for (const found of text.matchAll(ATTRIBUTE)) attrs[found[1].toLowerCase()] = decode(found[2] ?? found[3] ?? found[4] ?? "");
  return attrs;
}

function tags(markup: string): Tag[] {
  const found: Tag[] = [];
  TOKEN.lastIndex = 0;
  for (let match = TOKEN.exec(markup); match; match = TOKEN.exec(markup)) {
    if (match[0].startsWith("<!--")) continue;
    const tag = { closing: match[1] === "/", name: match[2].toLowerCase(), attrs: attributesOf(match[3]), start: match.index, end: TOKEN.lastIndex, selfClosing: match[4] === "/" };
    found.push(tag);
    if (!tag.closing && RAW_TEXT.has(tag.name)) TOKEN.lastIndex = markup.indexOf(`</${tag.name}`, TOKEN.lastIndex);
  }
  return found;
}

function anchorTest(anchor: string): (tag: Tag) => boolean {
  const byId = /^#(.+)$/.exec(anchor);
  if (byId) return (tag) => tag.attrs.id === byId[1];
  const byAttribute = /^\[([a-z-]+)="([^"]*)"\]$/.exec(anchor);
  if (!byAttribute) throw new RangeError(`No anchor form ${anchor}`);
  return (tag) => tag.attrs[byAttribute[1]] === byAttribute[2];
}

function elementRange(markup: string, all: Tag[], anchor: string): [number, number] {
  const test = anchorTest(anchor);
  const starts = all.filter((tag) => !tag.closing && test(tag));
  if (starts.length !== 1) throw new RangeError(`${anchor} matches ${starts.length} elements`);
  const open = starts[0];
  if (open.selfClosing || VOID.has(open.name)) return [open.start, open.end];
  let depth = 0;
  for (const tag of all.slice(all.indexOf(open))) {
    if (tag.name !== open.name || tag.selfClosing) continue;
    depth += tag.closing ? -1 : 1;
    if (depth === 0) return [open.start, tag.end];
  }
  throw new RangeError(`${anchor} is never closed`);
}

export function approvedMarkup(anchor: string, without: readonly string[] = []): string {
  const markup = approvedTemplate();
  const all = tags(markup);
  const [start, end] = elementRange(markup, all, anchor);
  const cuts = without.map((nested) => elementRange(markup, all, nested)).sort((a, b) => a[0] - b[0]);
  let kept = "";
  let at = start;
  for (const [cutStart, cutEnd] of cuts) {
    kept += markup.slice(at, cutStart);
    at = cutEnd;
  }
  return kept + markup.slice(at, end);
}

function canonicalValue(name: string, value: string): string {
  if (name === "class") return value.split(/\s+/).filter(Boolean).sort().join(" ");
  if (name === "style")
    return value
      .split(";")
      .map((rule) => rule.split(":").map((part) => part.trim()).join(":"))
      .filter((rule) => rule !== "" && rule !== ":")
      .sort()
      .join(";");
  return value;
}

export function canonical(markup: string): string[] {
  const out: string[] = [];
  let at = 0;
  const text = (raw: string) => {
    const shown = decode(raw).replace(/\s+/g, " ").trim();
    if (shown) out.push(`#${shown}`);
  };
  for (const tag of tags(markup)) {
    text(markup.slice(at, tag.start));
    at = tag.end;
    if (tag.closing) {
      out.push(`</${tag.name}>`);
      continue;
    }
    const attrs = Object.keys(tag.attrs)
      .filter((name) => tag.name !== "img" || !PICTURE_DELIVERY.has(name.toLowerCase()))
      .sort()
      .map((name) => `${name}="${canonicalValue(name, tag.attrs[name])}"`);
    out.push(`<${[tag.name, ...attrs].join(" ")}>`);
    if (tag.selfClosing || VOID.has(tag.name)) out.push(`</${tag.name}>`);
  }
  text(markup.slice(at));
  return out;
}

function componentNamed(label: string): MonographComponent | undefined {
  return approvedContent().components.find((component) => component.label === label);
}

function viewProps(component: MonographComponent, views: ComponentViews): NestingViewProps {
  const renderComponent = (label: string): ReactNode => {
    const held = componentNamed(label);
    const view = held ? views[held.kind] : undefined;
    return held && view ? createElement(() => view(viewProps(held, views))) : null;
  };
  return { component, spec: specOf(component.label), unitRefs: unitsWithin(component.label), renderUnit: (ref: string) => createElement("kv-slot", { unit: ref }), renderComponent };
}

export function drawnView(view: ComponentView, component: MonographComponent, views: ComponentViews = {}): string {
  return renderToStaticMarkup(createElement(() => view(viewProps(component, views)))).replace(HOISTED_PRELOAD, "");
}

export function anchorsHeldWithoutView(component: MonographComponent, views: ComponentViews): string[] {
  const labels = new Set(approvedContent().components.map((entry) => entry.label));
  return componentsHeldBy(specOf(component.label), labels)
    .map(componentNamed)
    .filter((held): held is MonographComponent => held !== undefined && !views[held.kind])
    .map(anchorOf);
}

export function anchorOf(component: MonographComponent): string {
  return ANCHOR_CORRECTIONS[component.label] ?? component.anchor;
}
