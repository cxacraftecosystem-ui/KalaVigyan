import { clusterName } from "@/lib/citationCluster";
import type { MonographMark, MonographNode, MonographSource } from "@/lib/monographDocument";

export const ITALIC_ROLES = ["loc", "bot", "ring", "on"] as const;
export const MARK_TAGS: Readonly<Record<string, string>> = { b: "b", sub: "sub", sup: "sup", mark: "mark" };
const SENTENCE_ATTRS: readonly (readonly [string, string])[] = [["src", "data-src"], ["sid", "data-sid"], ["pair", "data-pair"]];
const LINK_ATTRS: readonly (readonly [string, string])[] = [["rel", "rel"], ["target", "target"], ["ask", "data-ask"], ["lang", "lang"]];
const CLASS_NAMES = /^[A-Za-z0-9_ -]+$/;
const SAFE_HREF = /^(#|\/(?!\/)|https?:\/\/|mailto:)/i;

export type MonographSources = Readonly<Record<string, MonographSource>>;
export type Attribute = readonly [string, string];
export type MarkupPart = { tag: string; attrs: readonly Attribute[]; children: readonly Markup[] };
export type Markup = MarkupPart | string;

export class MonographMarkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MonographMarkError";
  }
}

export function escapeText(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function escapeAttribute(value: string): string {
  return escapeText(value).replace(/"/g, "&quot;").replace(/'/g, "&#x27;");
}

export function renderNodes(nodes: readonly MonographNode[], sources: MonographSources): string {
  return markupHtml(markupOf(nodes, sources));
}

export function markupHtml(parts: readonly Markup[]): string {
  return parts.map((part) => (typeof part === "string" ? escapeText(part) : partHtml(part))).join("");
}

function partHtml(part: MarkupPart): string {
  const attrs = part.attrs.map(([name, value]) => ` ${name}="${escapeAttribute(value)}"`).join("");
  return `<${part.tag}${attrs}>${markupHtml(part.children)}</${part.tag}>`;
}

export function markupOf(nodes: readonly MonographNode[], sources: MonographSources): Markup[] {
  return nodes.map((node) => (typeof node === "string" ? node : markOf(node, sources)));
}

function markOf(node: MonographMark, sources: MonographSources): MarkupPart {
  const children = markupOf(node.c ?? [], sources);
  const describe = MARKS[node.m];
  if (describe) return describe(node, children, sources);
  const tag = Object.hasOwn(MARK_TAGS, node.m) ? MARK_TAGS[node.m] : null;
  if (tag) return { tag, attrs: [], children };
  throw new MonographMarkError(`No inline mark ${JSON.stringify(node.m)}`);
}

type MarkDescriber = (node: MonographMark, children: Markup[], sources: MonographSources) => MarkupPart;

const MARKS: Readonly<Record<string, MarkDescriber>> = {
  s: (node, children) => ({ tag: "span", attrs: [["class", node.cls ? `s ${className(node.cls)}` : "s"], ...attributes(node, SENTENCE_ATTRS)], children }),
  span: (node, children) => ({ tag: "span", attrs: node.cls ? [["class", className(node.cls)]] : [], children }),
  cite: (node, children, sources) => ({ tag: "span", attrs: [["class", "nw"]], children: [...children, citeButton(node, sources)] }),
  i: (node, children) => ({ tag: "i", attrs: italicRole(node), children }),
  link: (node, children) => ({ tag: "a", attrs: linkAttributes(node), children }),
  figref: (node, children) => ({ tag: "span", attrs: [["class", "kv-figref"], ["data-figref", field(node, "ref")]], children })
};

function field(node: MonographMark, key: string): string {
  const value = node[key];
  if (typeof value !== "string") throw new MonographMarkError(`The ${node.m} mark needs a text ${key}`);
  return value;
}

function className(value: unknown): string {
  if (typeof value !== "string" || !CLASS_NAMES.test(value)) throw new MonographMarkError(`No class ${JSON.stringify(value)}`);
  return value;
}

function attributes(node: MonographMark, names: readonly Attribute[]): Attribute[] {
  return names.filter(([key]) => node[key] !== undefined && node[key] !== null).map(([key, attribute]) => [attribute, field(node, key)] as const);
}

function italicRole(node: MonographMark): Attribute[] {
  const role = node.role;
  if (role === undefined || role === null) return [];
  if (!(ITALIC_ROLES as readonly unknown[]).includes(role)) throw new MonographMarkError(`No italic role ${JSON.stringify(role)}`);
  return [["class", role as string]];
}

function linkAttributes(node: MonographMark): Attribute[] {
  const href = field(node, "href");
  if (!SAFE_HREF.test(href)) throw new MonographMarkError(`A link may not go to ${JSON.stringify(href)}`);
  if (node.cls) return [["class", className(node.cls)], ["href", href]];
  return [["href", href], ...attributes(node, LINK_ATTRS)];
}

export type CitedNumbers = { numbers: string[]; label: string; described: string };

export function citedNumbers(keys: readonly string[], sources: MonographSources): CitedNumbers {
  const missing = keys.filter((key) => !Object.hasOwn(sources, key));
  if (missing.length) throw new MonographMarkError(`A citation names unknown sources ${missing.join(", ")}`);
  const byNumber = new Map(keys.map((key) => [sources[key].number, sources[key]] as const));
  const shown = [...byNumber.entries()].sort(([a], [b]) => a - b);
  const numbers = shown.map(([number]) => String(number));
  return { numbers, label: clusterName(shown.map(([number]) => ({ number }))), described: shown.map(([, source]) => source.title).join("; ") };
}

export function citeButton(node: MonographMark, sources: MonographSources): MarkupPart {
  const keys = node.g;
  if (!Array.isArray(keys) || !keys.every((key) => typeof key === "string")) throw new MonographMarkError("A citation lists its sources in g");
  const cited = citedNumbers(keys, sources);
  return {
    tag: "button",
    attrs: [
      ["class", "kcite"],
      ["type", "button"],
      ["data-c", field(node, "key")],
      ["data-g", keys.join(" ")],
      ["aria-haspopup", "dialog"],
      ["aria-expanded", "false"],
      ["aria-label", cited.label],
      ["aria-description", cited.described]
    ],
    children: [cited.numbers.join(",")]
  };
}

export function nodesText(nodes: readonly MonographNode[]): string {
  return nodes.map((node) => (typeof node === "string" ? node : nodesText(node.c ?? []))).join("");
}

export function hasSentence(nodes: readonly MonographNode[]): boolean {
  return nodes.some((node) => typeof node !== "string" && (node.m === "s" || node.m === "cite" || hasSentence(node.c ?? [])));
}

export function citedSourceKeys(nodes: readonly MonographNode[]): string[] {
  return nodes.flatMap((node) => {
    if (typeof node === "string") return [];
    const own = node.m === "cite" && Array.isArray(node.g) ? (node.g as string[]) : [];
    return [...own, ...citedSourceKeys(node.c ?? [])];
  });
}
