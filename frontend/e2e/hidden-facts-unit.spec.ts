import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { HIDDEN_SUMMARY, hiddenRows, hiddenSummary, hiddenTotal, parseHiddenFacts, type HiddenFacts, type HiddenFactsReport } from "@/lib/hiddenFacts";
import { ShapeError } from "@/lib/shape";

const UNEXPLAINED_FACT = "0b7c2f5e-7a1d-5a43-9a51-2f8a1c6d9e10";
const ADMIN_PAGE = join(__dirname, "..", "app", "(protected)", "admin", "page.tsx");
const counted = () => "23 Nov 2026";

function report(changes: Partial<HiddenFactsReport> = {}): HiddenFactsReport {
  return {
    countedAt: "2026-11-23T01:10:00+05:30",
    crafts: 3,
    byReason: { HELD: 2, RESTRICTED_FACT: 1, HIDDEN_CONCEPT: 0, NO_SHOWN_SOURCE: 3 },
    unexplained: 1,
    craftsUnexplained: ["Bagh-Print"],
    perCraft: [
      { craft: "Bagh-Print", approved: 40, hidden: { HELD: 1 }, unexplained: [UNEXPLAINED_FACT] },
      { craft: "Bagru-Hand-Block-Print", approved: 12, hidden: { HELD: 1 }, unexplained: [] },
      { craft: "Kutch-Ajrakh", approved: 120, hidden: { NO_SHOWN_SOURCE: 3, RESTRICTED_FACT: 1 }, unexplained: [] }
    ],
    ...changes
  };
}

const found = (changes: Partial<HiddenFactsReport> = {}): HiddenFacts => ({ report: report(changes) });

test("the night's report parses as the route sends it, and before the first night as null", () => {
  expect(parseHiddenFacts(found())).toEqual(found());
  expect(parseHiddenFacts({ report: null })).toEqual({ report: null });
});

test("a report off its shape is refused", () => {
  const { HELD: _held, ...withoutHeld } = report().byReason;
  expect(() => parseHiddenFacts({ report: { ...report(), byReason: withoutHeld } })).toThrow(ShapeError);
  expect(() => parseHiddenFacts(found({ perCraft: [{ craft: "Bagh-Print", approved: 40, hidden: { LOST: 1 } as never, unexplained: [] }] }))).toThrow(ShapeError);
  expect(() => parseHiddenFacts(found({ perCraft: [{ craft: "Bagh-Print", approved: 40, hidden: {}, unexplained: ["fact 1"] }] }))).toThrow(ShapeError);
  expect(() => parseHiddenFacts(found({ crafts: -1 }))).toThrow(ShapeError);
  expect(() => parseHiddenFacts({})).toThrow(ShapeError);
});

test("each craft lists its hidden facts by reason, the crafts with unexplained facts first, then the most hidden", () => {
  expect(hiddenRows(report())).toEqual([
    { craft: "Bagh-Print", approved: 40, reasons: { HELD: 1, RESTRICTED_FACT: 0, HIDDEN_CONCEPT: 0, NO_SHOWN_SOURCE: 0 }, unexplained: 1, hidden: 2 },
    { craft: "Kutch-Ajrakh", approved: 120, reasons: { HELD: 0, RESTRICTED_FACT: 1, HIDDEN_CONCEPT: 0, NO_SHOWN_SOURCE: 3 }, unexplained: 0, hidden: 4 },
    { craft: "Bagru-Hand-Block-Print", approved: 12, reasons: { HELD: 1, RESTRICTED_FACT: 0, HIDDEN_CONCEPT: 0, NO_SHOWN_SOURCE: 0 }, unexplained: 0, hidden: 1 }
  ]);
  expect(hiddenTotal(report())).toBe(7);
});

test("the summary says when the night counted, how many facts hide in how many crafts and how many no rule explains", () => {
  expect(hiddenSummary(found(), counted)).toBe("Counted 23 Nov 2026: 7 hidden facts in 3 crafts, 1 unexplained in 1 craft.");
  expect(hiddenSummary(found({ crafts: 4 }), counted)).toBe("Counted 23 Nov 2026: 7 hidden facts in 4 crafts, 1 unexplained in 1 craft. The first 3 by address are listed.");
  const explained = found({ unexplained: 0, craftsUnexplained: [], byReason: { HELD: 1, RESTRICTED_FACT: 0, HIDDEN_CONCEPT: 0, NO_SHOWN_SOURCE: 0 }, crafts: 1, perCraft: [{ craft: "Bagru-Hand-Block-Print", approved: 12, hidden: { HELD: 1 }, unexplained: [] }] });
  expect(hiddenSummary(explained, counted)).toBe("Counted 23 Nov 2026: 1 hidden fact in 1 craft.");
  expect(hiddenSummary(found({ crafts: 0, unexplained: 0, craftsUnexplained: [], perCraft: [], byReason: { HELD: 0, RESTRICTED_FACT: 0, HIDDEN_CONCEPT: 0, NO_SHOWN_SOURCE: 0 } }), counted)).toBe(`Counted 23 Nov 2026. ${HIDDEN_SUMMARY.allShown}`);
  expect(hiddenSummary({ report: null }, counted)).toBe(HIDDEN_SUMMARY.waiting);
});

test("the settings hub draws the card", () => {
  expect(readFileSync(ADMIN_PAGE, "utf8")).toContain("<HiddenFactsCard />");
});
