export type LayerKind = "places" | "land" | "districts";

export type LayerChoice = { kind: LayerKind; index: number };

export type CitationMode = "sheet" | "popover";

export type Theme = "light" | "dark";

export const SHEET_BELOW_PX = 640;
export const DIPS = 4;
export const PLACES: LayerChoice = { kind: "places", index: 0 };

const SWITCH_TEMPLATE: readonly LayerChoice[] = [
  { kind: "land", index: 0 },
  { kind: "land", index: 1 },
  { kind: "districts", index: 0 },
  { kind: "districts", index: 1 },
  PLACES,
  { kind: "districts", index: 2 },
  { kind: "land", index: 2 },
  PLACES
];

function available(choice: LayerChoice, land: number, districts: number): LayerChoice | null {
  if (choice.kind === "places") return choice;
  const count = choice.kind === "land" ? land : districts;
  if (count === 0) return null;
  if (choice.index < count) return choice;
  return choice.kind === "districts" && choice.index === 1 ? null : { kind: choice.kind, index: choice.index % count };
}

function sameChoice(a: LayerChoice | undefined, b: LayerChoice): boolean {
  return a !== undefined && a.kind === b.kind && a.index === b.index;
}

export function layerSwitches(land: number, districts: number): LayerChoice[] {
  const walked: LayerChoice[] = [];
  for (const wanted of SWITCH_TEMPLATE) {
    const choice = available(wanted, land, districts);
    const last = walked.length ? walked[walked.length - 1] : PLACES;
    if (choice && !sameChoice(last, choice)) walked.push(choice);
  }
  return walked;
}

export function switchKinds(choices: readonly LayerChoice[]): string[] {
  return choices.map((choice, at) => `${(at === 0 ? PLACES : choices[at - 1]).kind} to ${choice.kind}`);
}

export function optionIndex(choice: LayerChoice, land: number): number | null {
  if (choice.kind === "places") return null;
  return choice.kind === "land" ? choice.index : land + choice.index;
}

export function citationMode(width: number): CitationMode {
  return width < SHEET_BELOW_PX ? "sheet" : "popover";
}

export function flippedTheme(theme: Theme): Theme {
  return theme === "dark" ? "light" : "dark";
}

export function nextDips(dips: number): number {
  return dips >= DIPS ? 1 : dips + 1;
}

export function otherStep(current: number, steps: number): number | null {
  if (steps < 2) return null;
  return current >= steps ? 1 : current + 1;
}

export function endsOnItsOwn(step: number, steps: number): boolean {
  return step >= steps;
}

export function otherChoice(values: readonly string[], pressed: string | null): string | null {
  return values.find((value) => value !== pressed) ?? null;
}

export function unchangedProblems(control: string, before: string, after: string): string[] {
  return before === after ? [`${control} left its state unchanged at "${before}"`] : [];
}

export function expectedProblems(control: string, expected: string, after: string): string[] {
  return after === expected ? [] : [`${control} shows "${after}"; it should show "${expected}"`];
}
