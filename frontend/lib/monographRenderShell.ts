import { isDocumentLanguage, type DocumentLanguageCode } from "@/lib/documentLanguages";
import type { MonographDocument } from "@/lib/monographDocument";
import type { MonographSources } from "@/lib/monographRender";
import { bundleSources, kitDataBlocks, type KitDataBlock } from "@/lib/monographRenderKit";
import { componentBundles, type ComponentBundle } from "@/lib/monographRenderLayout";
import { shellSlots, shellTree, type ShellNode } from "@/lib/monographShellTree";

export const SHELL_REST_SCHEMA_VERSION = 1;
export const DOCUMENT_REST_SCHEMA_VERSION = 1;
export const LEAD_CHAPTERS = 1;
const CATEGORY_SUBJECT = "category";
const CHAPTER_CLASS = "kv-ch";
const CHAPTER_TAG = "section";
const PICTURE_KEYS = ["src", "width", "height", "alt", "loading"] as const;
const DIGEST_SEED = 0x811c9dc5;
const DIGEST_PRIME = 0x01000193;
const DIGEST_CHARS = 8;
const REST_ADDRESS = /^v([1-9]\d*)(?:-([0-9a-f]{8})(?:-([a-z]{2,3}))?)?$/;

export type ShellPart = { tree: ShellNode[]; bundles: Record<string, ComponentBundle>; sources: MonographSources };
export type ShellRest = ShellPart & { schemaVersion: typeof SHELL_REST_SCHEMA_VERSION; version: number; data: KitDataBlock[] };
export type ShellParts = { lead: ShellPart; rest: ShellPart };
export type DocumentRest = { schemaVersion: typeof DOCUMENT_REST_SCHEMA_VERSION; version: number; document: MonographDocument };
export type RestPart = "shell" | "document";
export type RestAddress = { version: number; digest: string | null; language: DocumentLanguageCode | null };

export function shellRestPath(slug: string, version: number, subject = "craft", digest: string | null = null, language: DocumentLanguageCode | null = null): string {
  const pages = subject === CATEGORY_SUBJECT ? "categories" : "crafts";
  const variant = digest && language ? `-${language}` : "";
  return `/${pages}/${encodeURIComponent(slug)}/shell/v${version}${digest ? `-${digest}` : ""}${variant}`;
}

export function restAddress(segment: string): RestAddress | null {
  const found = REST_ADDRESS.exec(segment);
  if (!found) return null;
  const language = found[3] ?? null;
  if (language !== null && !isDocumentLanguage(language)) return null;
  return { version: Number(found[1]), digest: found[2] ?? null, language };
}

export function documentDigest(document: MonographDocument): string {
  const text = JSON.stringify([document.content, document.specs, document.fragments]);
  let hash = DIGEST_SEED;
  for (let at = 0; at < text.length; at += 1) hash = Math.imul(hash ^ text.charCodeAt(at), DIGEST_PRIME);
  return (hash >>> 0).toString(16).padStart(DIGEST_CHARS, "0");
}

export function leadChapters<T>(chapters: readonly T[]): T[] {
  return chapters.slice(0, LEAD_CHAPTERS);
}

export function restChapters<T>(chapters: readonly T[]): T[] {
  return chapters.slice(LEAD_CHAPTERS);
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

export function documentRest(document: MonographDocument): DocumentRest {
  return { schemaVersion: DOCUMENT_REST_SCHEMA_VERSION, version: document.version, document: { ...document, specs: lazyPictures(document.specs) } };
}

export function restBody(document: MonographDocument): ShellRest | DocumentRest {
  return document.shell === null ? documentRest(document) : shellRest(document);
}

export function checkedDocumentRest(raw: unknown, version: number): DocumentRest {
  const body = raw as Partial<DocumentRest> | null;
  const document = body?.document as Partial<MonographDocument> | undefined;
  if (!body || body.schemaVersion !== DOCUMENT_REST_SCHEMA_VERSION || body.version !== version || !document || document.version !== version || document.shell !== null || typeof document.content !== "object" || document.content === null) {
    throw new Error(`The rest of monograph version ${version} came back in another shape`);
  }
  return body as DocumentRest;
}
