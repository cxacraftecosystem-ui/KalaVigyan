import { expect, test } from "@playwright/test";

import { reviewQueuePageShape, type StructureItem, type StructureReview } from "@/lib/reviewQueueContract";
import { KIND_LABELS, KIND_NOUNS, gateLine, kindTabs } from "@/lib/reviewQueueView";
import { parseShape } from "@/lib/shape";
import { checkLines, entryLines, speciesLine, structureActions, targetLine, writesLine } from "@/lib/structureReviewView";

const NAME = { kind: "NATIVE_NAME", text: "Ajrak", language: "sd", script: "Latn" };
const QUOTE = { text: "Printers here call the cloth ajrak, from the word for blue", locator: "para 1" };

const REVIEW = {
  kind: "NATIVE_NAME",
  subject: { kind: "craft", slug: "Kutch-Ajrakh" },
  subjectName: "Kutch Ajrakh",
  pageUrl: "https://kalavigyan.example/crafts/Kutch-Ajrakh",
  target: null,
  current: null,
  item: NAME,
  statement: "Printers in the delta call the cloth ajrak, after their word for blue.",
  field: "HISTORY",
  note: null,
  taskKey: null,
  sources: [{ title: "Dyeing in the delta", url: "https://crafts.example.org/dyeing", licence: null, reliability: "C", quotes: [QUOTE] }],
  checks: [
    { check: "STATED", passed: true, reasons: ["Every name and number it gives is in one of its quotes: the native name."] },
    { check: "QUOTES", passed: true, reasons: ["Every quote was found verbatim."] }
  ],
  conflicting: [],
  stale: null
};

const ITEM = {
  id: "00000000-0000-4000-8000-000000000011",
  origin: "AGENT",
  submittedAt: "2026-11-20T09:00:00Z",
  craft: { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" },
  proposer: null,
  kind: "STRUCTURE",
  structure: REVIEW
};

const PAGE = {
  schemaVersion: 1,
  kinds: ["FACTS", "TESTIMONY", "STRUCTURE"],
  counts: { FACTS: 0, TESTIMONY: 0, STRUCTURE: 1 },
  total: 1,
  items: [ITEM],
  nextCursor: null
};

function review(changes: Partial<StructureReview>): StructureReview {
  return { ...(REVIEW as StructureReview), ...changes };
}

test("a structure proposal from the server is read with its item, and an unknown item kind is refused", () => {
  const page = parseShape(reviewQueuePageShape, PAGE);
  const item = page.items[0] as StructureItem;
  expect([item.kind, item.structure.kind, item.structure.item.kind]).toEqual(["STRUCTURE", "NATIVE_NAME", "NATIVE_NAME"]);
  const wrong = { ...ITEM, structure: { ...REVIEW, item: { kind: "SPELLING", text: "x" } } };
  expect(() => parseShape(reviewQueuePageShape, { ...PAGE, items: [wrong] })).toThrow();
  const extra = { ...ITEM, structure: { ...REVIEW, item: { ...NAME, gloss: "blue" } } };
  expect(() => parseShape(reviewQueuePageShape, { ...PAGE, items: [extra] })).toThrow();
});

test("the structure tab carries its count and its own names", () => {
  expect(kindTabs(parseShape(reviewQueuePageShape, PAGE)).at(-1)?.label).toBe("Structure (1)");
  expect([KIND_LABELS.STRUCTURE, KIND_NOUNS.STRUCTURE]).toEqual(["Structure", "Structure proposal"]);
});

test("a native name carries its language and script for the page to set its face", () => {
  expect(entryLines(review({}).item)).toEqual([
    { term: "Name", value: "Ajrak", lang: "sd", script: "Latn" },
    { term: "Language", value: "sd" }
  ]);
});

test("a reaction names its species with their formulas and a GI record only the parts it gives", () => {
  const reaction = {
    kind: "REACTION" as const,
    reactionKind: "COMPLEXATION",
    stageKey: "P01",
    reactants: [{ name: "alum", formula: "KAl(SO4)2" }, { name: "alizarin", formula: null }],
    products: [{ name: "lake", formula: null }]
  };
  expect(speciesLine(reaction.reactants)).toBe("alum (KAl(SO4)2) + alizarin");
  expect(entryLines(reaction).map((line) => line.term)).toEqual(["Kind", "Reactants", "Products"]);
  const gi = {
    kind: "GI_RECORD" as const,
    applicationNumber: "182",
    certificateNumber: null,
    filedOn: null,
    registeredOn: "2009-03-10",
    journalIssue: null,
    proprietors: ["Ajrakh printers' society"],
    authorisedUserCount: 0
  };
  expect(entryLines(gi)).toEqual([
    { term: "Application number", value: "182" },
    { term: "Registered on", value: "2009-03-10" },
    { term: "Authorised users", value: "0" },
    { term: "Proprietors", value: "Ajrakh printers' society" }
  ]);
});

test("the checks read as the queue's gate lines", () => {
  const [stated, quotes] = checkLines(review({}).checks);
  expect(gateLine(stated)).toBe("Every name and number given is in a quote: passed");
  expect(gateLine(quotes)).toBe("Quotes found in the source: passed");
});

test("a proposal the page has moved past can only be rejected, and says why", () => {
  expect(structureActions(review({}))).toEqual(["approve", "reject"]);
  const stale = review({ stale: "P01 is not a stage of this page" });
  expect(structureActions(stale)).toEqual(["reject"]);
  expect(writesLine(stale)).toBe("The page has moved on, so it can only be rejected: P01 is not a stage of this page.");
  expect(writesLine(review({}))).toBe("Approving writes it into the Kutch Ajrakh page and its dossier, with its fact cited.");
  expect(targetLine(review({ target: "Stage P01, Second wash" }))).toBe("Kutch Ajrakh · Stage P01, Second wash");
});
