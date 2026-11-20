import type { MonographDocument } from "@/lib/monographDocument";
import type { MonographSources } from "@/lib/monographRender";
import { bundleSources, kitDataBlocks, type KitDataBlock } from "@/lib/monographRenderKit";
import { componentBundles, type ComponentBundle } from "@/lib/monographRenderLayout";
import { shellSlots, shellTree, type ShellNode } from "@/lib/monographShellTree";

export const SHELL_REST_SCHEMA_VERSION = 1;
const CHAPTER_CLASS = "kv-ch";
const CHAPTER_TAG = "section";
const PICTURE_KEYS = ["src", "width", "height", "alt", "loading"] as const;

export type ShellPart = { tree: ShellNode[]; bundles: Record<string, ComponentBundle>; sources: MonographSources };
export type ShellRest = ShellPart & { schemaVersion: typeof SHELL_REST_SCHEMA_VERSION; version: number; data: KitDataBlock[] };
export type ShellParts = { lead: ShellPart; rest: ShellPart };

export function shellRestPath(slug: string, version: number): string {
  return `/crafts/${encodeURIComponent(slug)}/shell/v${version}`;
}

export function isChapter(node: ShellNode): boolean {
  if (node.kind !== "element" && node.kind !== "held") return false;
  return node.tag === CHAPTER_TAG && (node.attrs.class ?? "").split(/\s+/).includes(CHAPTER_CLASS);
}

export function leadLength(tree: readonly ShellNode[]): number {
  const first = tree.findIndex(isChapter);
  return first < 0 ? tree.length : first + 1;
}

export function slotBundles(document: MonographDocument, labels: readonly string[]): Record<string, ComponentBundle> {
  return Object.assign({}, ...labels.map((label) => componentBundles(document, label)));
}

export function shellPart(document: MonographDocument, tree: ShellNode[]): ShellPart {
  const bundles = slotBundles(document, shellSlots(tree));
  return { tree, bundles, sources: bundleSources(document, bundles) };
}

export function documentTree(document: MonographDocument): ShellNode[] {
  return shellTree(document.shell ?? "", new Set(Object.keys(document.specs)));
}

export function shellParts(document: MonographDocument): ShellParts {
  const tree = documentTree(document);
  const cut = leadLength(tree);
  return { lead: shellPart(document, tree.slice(0, cut)), rest: shellPart(document, tree.slice(cut)) };
}

function isPicture(value: Record<string, unknown>): boolean {
  return PICTURE_KEYS.every((key) => Object.hasOwn(value, key)) && typeof value.src === "string";
}

export function lazyPictures<T>(value: T): T {
  if (Array.isArray(value)) return value.map((item) => lazyPictures(item)) as T;
  if (value === null || typeof value !== "object") return value;
  const record = value as Record<string, unknown>;
  if (isPicture(record)) return { ...record, loading: "lazy", fetchPriority: null } as T;
  return Object.fromEntries(Object.entries(record).map(([key, item]) => [key, lazyPictures(item)])) as T;
}

export function shellRest(document: MonographDocument): ShellRest {
  const { rest } = shellParts(document);
  const bundles = Object.fromEntries(Object.entries(rest.bundles).map(([label, bundle]) => [label, { ...bundle, spec: lazyPictures(bundle.spec) }]));
  return { schemaVersion: SHELL_REST_SCHEMA_VERSION, version: document.version, tree: rest.tree, bundles, sources: rest.sources, data: kitDataBlocks(document.content) };
}

export function checkedShellRest(raw: unknown, version: number): ShellRest {
  const body = raw as Partial<ShellRest> | null;
  if (!body || body.schemaVersion !== SHELL_REST_SCHEMA_VERSION || body.version !== version || !Array.isArray(body.tree) || !Array.isArray(body.data) || typeof body.bundles !== "object" || typeof body.sources !== "object") {
    throw new Error(`The rest of monograph version ${version} came back in another shape`);
  }
  return body as ShellRest;
}
