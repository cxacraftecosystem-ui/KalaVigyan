import type { ExplainerBlock } from "@/lib/explainerContract";
import type { ExplainerEvent } from "@/lib/explainerStream";

export type BuiltBlockSeen = { kind: string; sectionId: string; afterFirstBlockMs: number; shown: string };
type TimedBlock = { at: number; event: ExplainerEvent };

export const TIMED_KINDS: ReadonlySet<string> = new Set(["region_story", "seasons", "supply_map"]);
const KIND_NAMES: Readonly<Record<string, string>> = { region_story: "region story", seasons: "seasons block", supply_map: "supply map" };

function counted(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

export function shownOf(block: ExplainerBlock): string {
  if (block.kind === "region_story") {
    const river = block.river ? `the ${block.river.name ?? "unnamed"} river over ${counted(block.river.reachIds.length, "reach", "reaches")}` : "no river";
    return `${counted(block.steps.length, "step", "steps")}, ${river}`;
  }
  if (block.kind === "seasons") {
    const timed = block.rows.filter((row) => row.months.length > 0 || row.season !== null).length;
    return `${counted(block.rows.length, "row", "rows")} (${timed} timed), ${block.rainfall ? "rainfall shown" : "no rainfall"}`;
  }
  if (block.kind === "supply_map") {
    const placed = block.links.filter((link) => link.latitude !== null && link.longitude !== null).length;
    return `${counted(block.links.length, "link", "links")}, ${counted(placed, "origin pinned", "origins pinned")}`;
  }
  return block.kind;
}

export function builtBlocks(events: readonly TimedBlock[]): BuiltBlockSeen[] {
  const firstBlockAt = new Map<string, number>();
  const seen: BuiltBlockSeen[] = [];
  for (const { at, event } of events) {
    if (event.type !== "block") continue;
    const { sectionId, block } = event.data;
    if (!firstBlockAt.has(sectionId)) firstBlockAt.set(sectionId, at);
    if (TIMED_KINDS.has(block.kind)) seen.push({ kind: block.kind, sectionId, afterFirstBlockMs: at - (firstBlockAt.get(sectionId) ?? at), shown: shownOf(block) });
  }
  return seen;
}

export function builtBlockNotes(seen: readonly BuiltBlockSeen[]): string[] {
  return seen.map((block) => `The ${KIND_NAMES[block.kind] ?? block.kind} of section ${block.sectionId} arrived ${(block.afterFirstBlockMs / 1000).toFixed(1)} s after its section's first block: ${block.shown}.`);
}
