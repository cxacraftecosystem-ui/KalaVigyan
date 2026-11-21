import type { MonographDocument } from "@/lib/monographDocument";
import { componentHome } from "@/lib/monographScopes";

export type KitDef = { scope: string | null; markup: string };
export type ScopedDefs = { scope: string | null; markup: string[] };
export type StyleReferences = Readonly<Record<string, readonly string[]>>;

export const STAGE_WEAVE = "pt-weave";
const TILE_PREFIX = "tile-";
const STAGE_KINDS = new Set(["stage_player"]);
const REFERENCE = /(?:url\(#|<use\s[^>]*?href=["']#|"(?:xlink:)?href":"#)([A-Za-z][\w-]*)/g;
const DEFINED = /(?:\sid=["']|"id":")([A-Za-z][\w-]*)/g;

export function referencedIds(text: string): string[] {
  return [...text.matchAll(REFERENCE)].map((found) => found[1]);
}

export function definedIds(text: string): string[] {
  return [...text.matchAll(DEFINED)].map((found) => found[1]);
}

export function usedDefs(texts: readonly string[], defs: Readonly<Record<string, KitDef>>, drawn: readonly string[] = []): KitDef[] {
  const own = new Set(texts.flatMap(definedIds));
  const chosen = new Map<string, KitDef>();
  const waiting = [...texts.flatMap(referencedIds), ...drawn];
  while (waiting.length) {
    const id = waiting.shift() as string;
    if (chosen.has(id) || own.has(id) || !Object.hasOwn(defs, id)) continue;
    chosen.set(id, defs[id]);
    waiting.push(...referencedIds(defs[id].markup));
  }
  return [...chosen.values()];
}

export function defsByScope(defs: readonly KitDef[]): ScopedDefs[] {
  const scopes = new Map<string | null, string[]>();
  for (const def of defs) scopes.set(def.scope, [...(scopes.get(def.scope) ?? []), def.markup]);
  return [...scopes].map(([scope, markup]) => ({ scope, markup }));
}

export function documentTexts(document: MonographDocument): string[] {
  return [JSON.stringify(document.specs), ...Object.values(document.fragments)];
}

function stageTiles(stages: readonly unknown[]): string[] {
  const tiled = stages.flatMap((stage, at) => (typeof stage === "object" && stage !== null && !(stage as { swatch?: unknown }).swatch ? [`${TILE_PREFIX}${at + 1}`] : []));
  return [...tiled, STAGE_WEAVE];
}

function namedIds(field: string, value: unknown): string[] {
  if ((field === "weave" || field === "tile") && typeof value === "string") return [value];
  if (field === "tile" && typeof value === "number") return [`${TILE_PREFIX}${value}`];
  return [];
}

function namedIn(value: unknown): string[] {
  if (Array.isArray(value)) return value.flatMap(namedIn);
  if (typeof value !== "object" || value === null) return [];
  return Object.entries(value).flatMap(([field, inner]) => [...namedIds(field, inner), ...namedIn(inner)]);
}

export function kitDrawnIds(kind: string, spec: unknown): string[] {
  const stages = STAGE_KINDS.has(kind) && typeof spec === "object" && spec !== null ? (spec as { stages?: unknown }).stages : undefined;
  return [...(Array.isArray(stages) ? stageTiles(stages) : []), ...namedIn(spec)];
}

export function drawnScopes(document: MonographDocument): string[] {
  const scopes = document.content.components.map((component) => {
    const spec = Object.hasOwn(document.specs, component.label) ? document.specs[component.label] : null;
    return componentHome(component.label, component.kind, spec).scope;
  });
  return [...new Set(scopes.filter((scope): scope is NonNullable<typeof scope> => scope !== null))];
}

export function pageDefs(document: MonographDocument, defs: Readonly<Record<string, KitDef>>, styled: StyleReferences): KitDef[] {
  const specs = document.content.components.flatMap((component) => (Object.hasOwn(document.specs, component.label) ? kitDrawnIds(component.kind, document.specs[component.label]) : []));
  const drawn = [...specs, ...drawnScopes(document).flatMap((scope) => styled[scope] ?? [])];
  return usedDefs(documentTexts(document), defs, drawn);
}
