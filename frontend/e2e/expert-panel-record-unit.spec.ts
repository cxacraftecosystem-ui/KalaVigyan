import { expect, test } from "@playwright/test";

import type { ExplainerBlock } from "@/lib/explainerContract";

import { NO_EXPERT_PANEL, NO_PANEL_NOTE, expertPanelNote, withExpertPanel } from "./production/expertPanel";

function view(seat: string, differs: number): ExplainerBlock {
  return { id: `s1.${seat.toLowerCase()}`, kind: "expert_view", version: 1, reuse: null, seat, take: [], agreesWith: [], differs: Array.from({ length: differs }, () => ({})) } as unknown as ExplainerBlock;
}

const PROSE = { id: "s1.b1", kind: "prose", version: 1, reuse: null, sentences: [] } as unknown as ExplainerBlock;

test("the Expert answer's record counts the panel's views and its mirrored Experts differ pairs", () => {
  const seen = [PROSE, view("HISTORIAN", 1), view("ANTHROPOLOGIST", 1), view("DESIGN_HISTORIAN", 0)].reduce(withExpertPanel, NO_EXPERT_PANEL);
  expect(seen).toEqual({ views: 3, seats: ["HISTORIAN", "ANTHROPOLOGIST", "DESIGN_HISTORIAN"], differences: 2 });
  expect(expertPanelNote(seen)).toBe("The expert panel gave 3 views (HISTORIAN, ANTHROPOLOGIST, DESIGN_HISTORIAN) and 1 Experts differ pair.");
});

test("an answer without a view says the panel's call was not seen working", () => {
  expect(expertPanelNote([PROSE].reduce(withExpertPanel, NO_EXPERT_PANEL))).toBe(NO_PANEL_NOTE);
  expect(expertPanelNote({ views: 1, seats: ["CHEMIST"], differences: 0 })).toBe("The expert panel gave 1 view (CHEMIST) and 0 Experts differ pairs.");
});
