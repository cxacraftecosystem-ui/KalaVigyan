import type { COLOUR_WORDS, ReactionStep, StepColour } from "@/lib/explainerMatter";
import { REACTION_KIND_LABEL, speciesName } from "@/lib/processView";
import type { ReactionSpecies } from "@/lib/scienceContract";

export const STEP_SECONDS = 4;

export type Playback = { at: number; playing: boolean };
export type PlaybackAction = { type: "play" | "pause" | "next" | "previous" | "tick" } | { type: "choose"; index: number };
export type CastRole = ReactionSpecies["role"];
export type CastMember = { key: string; formula: string | null; name: string };
export type StepSignal = "BALANCED" | "UNBALANCED";
export type ColourWord = (typeof COLOUR_WORDS)[number];
export type ColourChange = { before: StepColour | null; after: StepColour | null };

export const PLAYBACK_START: Playback = { at: 0, playing: false };

export const CAST_ROLE_LABEL: Record<CastRole, string> = { REACTANT: "Reactant", PRODUCT: "Product" };

export const COLOUR_LABEL: Record<ColourWord, string> = {
  RED: "Red",
  BLUE: "Blue",
  BLACK: "Black",
  WHITE: "White",
  GREEN: "Green",
  YELLOW: "Yellow",
  BROWN: "Brown",
  GREY: "Grey",
  PINK: "Pink",
  PURPLE: "Purple",
  ORANGE: "Orange",
  MAROON: "Maroon"
};

export const DYE_FILL: Record<ColourWord, string> = {
  RED: "var(--dye-madder-bright)",
  BLUE: "var(--dye-indigo)",
  BLACK: "var(--dye-kut)",
  WHITE: "var(--dye-cloth)",
  GREEN: "var(--dye-leuco)",
  YELLOW: "var(--dye-harda)",
  BROWN: "var(--dye-mud)",
  GREY: "var(--dye-lime-edge)",
  PINK: "var(--dye-pink)",
  PURPLE: "color-mix(in srgb, var(--dye-madder) 55%, var(--dye-indigo))",
  ORANGE: "var(--dye-kesari)",
  MAROON: "var(--dye-madder)"
};

export type ChangeMotion = "oxidise" | "dip";

export function changeMotion(change: ColourChange): ChangeMotion {
  return change.before?.colour === "GREEN" && change.after?.colour === "BLUE" ? "oxidise" : "dip";
}

function stepIndex(index: number, count: number): number {
  return Math.min(Math.max(0, Math.trunc(index)), Math.max(0, count - 1));
}

export function playable(count: number, reduce: boolean): boolean {
  return count > 1 && !reduce;
}

export function playbackStep(state: Playback, action: PlaybackAction, count: number): Playback {
  const last = count - 1;
  switch (action.type) {
    case "play":
      if (count < 2) return PLAYBACK_START;
      return { at: state.at >= last ? 0 : stepIndex(state.at, count), playing: true };
    case "pause":
      return { at: state.at, playing: false };
    case "next":
      return { at: stepIndex(state.at + 1, count), playing: false };
    case "previous":
      return { at: stepIndex(state.at - 1, count), playing: false };
    case "choose":
      return { at: stepIndex(action.index, count), playing: false };
    case "tick": {
      if (!state.playing) return state;
      const at = stepIndex(state.at + 1, count);
      return { at, playing: at < last };
    }
  }
}

export function castKey(species: ReactionSpecies): string {
  return species.formula ? `formula:${species.formula}` : `name:${speciesName(species).toLowerCase()}`;
}

export function reactionCast(steps: readonly ReactionStep[]): CastMember[] {
  const cast = new Map<string, CastMember>();
  for (const step of steps) {
    for (const species of step.species) {
      const key = castKey(species);
      if (!cast.has(key)) cast.set(key, { key, formula: species.formula, name: speciesName(species) });
    }
  }
  return [...cast.values()];
}

export function stepRoles(step: ReactionStep | null): ReadonlyMap<string, CastRole> {
  return new Map(step ? step.species.map((species) => [castKey(species), species.role] as const) : []);
}

export function stepSignal(step: Pick<ReactionStep, "balanced" | "equation">): StepSignal | null {
  if (step.balanced) return "BALANCED";
  return step.equation !== null ? "UNBALANCED" : null;
}

export function stepKindLabel(step: Pick<ReactionStep, "kind">): string {
  return REACTION_KIND_LABEL[step.kind];
}

export function stepPosition(at: number, count: number): string {
  return `Step ${stepIndex(at, count) + 1} of ${count}`;
}

export function colourChange(step: Pick<ReactionStep, "colours">): ColourChange | null {
  const colours = step.colours ?? [];
  const before = colours.find((colour) => colour.side === "BEFORE") ?? null;
  const after = colours.find((colour) => colour.side === "AFTER") ?? null;
  return before || after ? { before, after } : null;
}

export function colourChangeLine(change: ColourChange): string {
  const before = change.before ? COLOUR_LABEL[change.before.colour] : null;
  const after = change.after ? COLOUR_LABEL[change.after.colour] : null;
  if (before && after) return `${before} turns ${after.toLowerCase()}`;
  return before ? `${before} at first` : `${after ?? ""} as it forms`;
}

export function carriedKeys(steps: readonly ReactionStep[], at: number): ReadonlySet<string> {
  const sides = (index: number, role: CastRole) =>
    new Set((steps[index]?.species ?? []).filter((species) => species.role === role).map(castKey));
  const made = sides(at, "PRODUCT");
  const used = sides(at, "REACTANT");
  const next = sides(at + 1, "REACTANT");
  const previous = sides(at - 1, "PRODUCT");
  return new Set([...[...made].filter((key) => next.has(key)), ...[...used].filter((key) => previous.has(key))]);
}
