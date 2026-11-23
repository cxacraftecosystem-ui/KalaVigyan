import type { FactSource, Placement, QueueAction, StagePlacing } from "@/lib/reviewQueueContract";

export const PLACE_SEPARATOR = "|";
export const CHOOSE_PLACE = "Choose where the stage goes in the process before placing it.";

export type PlaceOption = { value: string; label: string; group: string };

export function placeOptions(placing: StagePlacing): PlaceOption[] {
  return placing.processes.flatMap((process) => {
    const [first] = process.stages;
    const start = { value: `${process.id}${PLACE_SEPARATOR}`, label: first ? `First, before ${first.name}` : "First", group: process.name };
    const after = process.stages.map((stage, index) => ({
      value: `${process.id}${PLACE_SEPARATOR}${stage.id}`,
      label: `After stage ${index + 1}, ${stage.name}`,
      group: process.name
    }));
    return [start, ...after];
  });
}

export function placementOf(value: string): Placement | null {
  const [processId, afterStageId] = value.split(PLACE_SEPARATOR);
  if (!processId) return null;
  return { processId, afterStageId: afterStageId || null };
}

export function placeProblem(action: QueueAction, value: string): string | null {
  return action === "approve" && !placementOf(value) ? CHOOSE_PLACE : null;
}

export function stageActions(): QueueAction[] {
  return ["approve", "reject"];
}

export function stageFactsLine(count: number): string {
  return count === 1 ? "The fact an answer found about it" : `The ${count} facts answers found about it`;
}

export function stageSources(placing: StagePlacing): FactSource[] {
  const merged = new Map<string, FactSource>();
  for (const source of placing.facts.flatMap((fact) => fact.sources)) {
    const key = `${source.title}${PLACE_SEPARATOR}${source.url ?? ""}`;
    const held = merged.get(key);
    const quotes = held ? [...held.quotes, ...source.quotes.filter((quote) => !held.quotes.some((kept) => kept.text === quote.text))] : source.quotes;
    merged.set(key, { ...(held ?? source), quotes });
  }
  return [...merged.values()];
}
