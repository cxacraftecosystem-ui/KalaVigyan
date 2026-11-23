import type { ExplainerBlock } from "@/lib/explainerContract";

export type ExpertPanelSeen = { views: number; seats: string[]; differences: number };

export const NO_EXPERT_PANEL: ExpertPanelSeen = { views: 0, seats: [], differences: 0 };
export const NO_PANEL_NOTE = "The expert panel gave no view in this answer, so its model call is not shown working here.";

export function withExpertPanel(seen: ExpertPanelSeen, block: ExplainerBlock): ExpertPanelSeen {
  if (block.kind !== "expert_view") return seen;
  return { views: seen.views + 1, seats: [...seen.seats, block.seat], differences: seen.differences + block.differs.length };
}

export function expertPanelNote(seen: ExpertPanelSeen): string {
  if (seen.views === 0) return NO_PANEL_NOTE;
  const pairs = Math.floor(seen.differences / 2);
  const views = seen.views === 1 ? "1 view" : `${seen.views} views`;
  return `The expert panel gave ${views} (${seen.seats.join(", ")}) and ${pairs} Experts differ ${pairs === 1 ? "pair" : "pairs"}.`;
}
