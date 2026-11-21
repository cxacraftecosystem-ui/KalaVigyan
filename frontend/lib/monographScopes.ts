import { COMPONENT_HOMES, type FrameStep, type HomeRecord } from "@/lib/componentHomes";
import { GENERAL_KINDS, isDeclared } from "@/lib/componentSpecsGeneral";

export type { FrameStep };

export type KitScope = "mb" | "chem" | "pt" | "rm" | "sa" | "ask";

export type KitFrame = "bare" | "screen" | "wrap" | "column";

export type ComponentPlace = { scope: KitScope; frame: KitFrame };

export type HomeSource = "home" | "kind" | "app";

export type ComponentHome = { scope: KitScope | null; frame: FrameStep[]; source: HomeSource };

const BOOK = COMPONENT_HOMES;

const PLACES: Readonly<Record<string, ComponentPlace>> = {
  ask_next: { scope: "rm", frame: "wrap" },
  audio_player: { scope: "rm", frame: "wrap" },
  chart: { scope: "mb", frame: "wrap" },
  citation_tool: { scope: "rm", frame: "bare" },
  comic: { scope: "sa", frame: "bare" },
  concept_atlas: { scope: "mb", frame: "wrap" },
  credits: { scope: "pt", frame: "screen" },
  diagram: { scope: "mb", frame: "wrap" },
  dip_player: { scope: "chem", frame: "wrap" },
  equation_card: { scope: "chem", frame: "wrap" },
  experiment_lab: { scope: "pt", frame: "wrap" },
  explainer: { scope: "mb", frame: "screen" },
  fact_table: { scope: "mb", frame: "wrap" },
  generator: { scope: "rm", frame: "bare" },
  label_card: { scope: "pt", frame: "wrap" },
  language_switch: { scope: "rm", frame: "wrap" },
  map_layer: { scope: "pt", frame: "wrap" },
  map_sequence: { scope: "pt", frame: "wrap" },
  material_cards: { scope: "chem", frame: "wrap" },
  model_explainer: { scope: "chem", frame: "wrap" },
  molecule_3d: { scope: "chem", frame: "wrap" },
  picture_plate: { scope: "pt", frame: "column" },
  process_replay: { scope: "ask", frame: "screen" },
  quiz: { scope: "rm", frame: "wrap" },
  reaction_player: { scope: "chem", frame: "wrap" },
  reading_level: { scope: "sa", frame: "bare" },
  related_crafts: { scope: "rm", frame: "wrap" },
  source_disagreements: { scope: "chem", frame: "wrap" },
  source_list: { scope: "rm", frame: "wrap" },
  specimen_plate: { scope: "mb", frame: "screen" },
  stage_player: { scope: "pt", frame: "wrap" },
  structure_diagram: { scope: "rm", frame: "wrap" },
  swatch_cards: { scope: "mb", frame: "screen" },
  timeline_map: { scope: "pt", frame: "wrap" },
  voice: { scope: "mb", frame: "bare" }
};

const UNKNOWN_PLACE: ComponentPlace = { scope: "mb", frame: "wrap" };

export const APP_KINDS: ReadonlySet<string> = new Set(["answer_block", "drawing", "why_here"]);
const DECLARED_KINDS: ReadonlySet<string> = new Set(GENERAL_KINDS);

export function appDrawn(kind: string, spec: Readonly<Record<string, unknown>> | null): boolean {
  return APP_KINDS.has(kind) || (DECLARED_KINDS.has(kind) && isDeclared(spec));
}

const SCREEN: FrameStep = { classes: ["screen"], box: true };
const PASSAGE: FrameStep = { classes: ["wrap", "kv-passage"], box: true };

export const FRAMES: Readonly<Record<KitFrame, FrameStep[]>> = {
  bare: [],
  screen: [SCREEN],
  wrap: [SCREEN, PASSAGE],
  column: [SCREEN, PASSAGE, { classes: ["spread"], box: true }, { classes: ["main"], box: true }]
};

const SCOPES: ReadonlySet<string> = new Set<KitScope>(["mb", "chem", "pt", "rm", "sa", "ask"]);

export function componentPlace(kind: string | null): ComponentPlace {
  return kind !== null && Object.hasOwn(PLACES, kind) ? PLACES[kind] : UNKNOWN_PLACE;
}

function kitScope(scope: string | null): KitScope | null {
  return scope !== null && SCOPES.has(scope) ? (scope as KitScope) : null;
}

export function specKeys(spec: Readonly<Record<string, unknown>> | null): string[] {
  if (!spec) return [];
  const filled = (value: unknown) => value !== null && value !== undefined && value !== "" && !(Array.isArray(value) && value.length === 0) && !(typeof value === "object" && !Array.isArray(value) && Object.keys(value as object).length === 0);
  return Object.keys(spec).filter((key) => filled(spec[key])).sort();
}

function overlap(keys: readonly string[], wanted: readonly string[]): number {
  if (keys.length === wanted.length && keys.every((key, at) => key === wanted[at])) return Number.POSITIVE_INFINITY;
  return keys.filter((key) => wanted.includes(key)).length;
}

export function kindScope(kind: string, spec: Readonly<Record<string, unknown>> | null): KitScope | null | undefined {
  const found = Object.hasOwn(BOOK.kinds, kind) ? BOOK.kinds[kind] : [];
  if (!found.length) return undefined;
  const keys = specKeys(spec);
  const scored = found.map((entry) => ({ scope: entry.scope, score: overlap(entry.keys, keys) }));
  const best = Math.max(...scored.map((entry) => entry.score));
  const scopes = new Set(scored.filter((entry) => entry.score === best).map((entry) => entry.scope));
  return scopes.size === 1 ? kitScope([...scopes][0]) : undefined;
}

export function authoredHome(label: string): HomeRecord | null {
  return Object.hasOwn(BOOK.homes, label) ? BOOK.homes[label] : null;
}

export function componentHome(label: string, kind: string, spec: Readonly<Record<string, unknown>> | null): ComponentHome {
  const place = componentPlace(kind);
  if (appDrawn(kind, spec)) return { scope: place.scope, frame: FRAMES[place.frame], source: "app" };
  const home = authoredHome(label);
  if (home && home.kind === kind) return { scope: kitScope(home.scope), frame: home.within ? FRAMES.wrap : home.frame, source: "home" };
  const derived = kindScope(kind, spec);
  return { scope: derived === undefined ? place.scope : derived, frame: FRAMES[place.frame], source: "kind" };
}
