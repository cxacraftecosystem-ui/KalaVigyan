import { expect, test } from "@playwright/test";

import { NAV_ITEMS } from "../components/DynamicIslandNav";
import { emptyFact, factBody, factFromTask, factProblems, proposalReplyShape, replyHeadline, type FactDraft, type ProposalReply } from "../lib/factProposalContract";
import {
  canWithdraw,
  itemsOfKind,
  kindLabel,
  openWorkFilter,
  ownProposalShape,
  removed,
  replaced,
  startingTasks,
  stateLabel,
  withdrawPath,
  withTerms,
  type OpenTask,
  type OwnProposal
} from "../lib/ownProposalsContract";
import { canAccessRoute, ROUTE_GUARDS } from "../lib/permissions";
import { parseShape } from "../lib/shape";
import type { User } from "../lib/types";

const QUOTE = "Alizarin binds to the alum mordant on the cloth.";

const DRAFT: FactDraft = {
  subjectKind: "craft",
  subjectSlug: "Kutch-Ajrakh",
  subjectName: "Kutch Ajrakh",
  field: "CHEMISTRY",
  fields: [],
  statement: "  Alizarin from madder binds to alum on the cloth as a red lake.  ",
  sources: [{ url: " https://example.org/madder ", title: " Madder dyeing ", licence: " ", quotes: [{ text: ` ${QUOTE} `, locator: "" }, { text: "  ", locator: "p. 4" }] }]
};

const ITEM: OwnProposal = {
  id: "0b7c4a52-3c0e-4d43-9a3f-111111111111",
  kind: "FACT",
  state: "WAITING",
  status: "DRAFT",
  text: "Alizarin binds to alum.",
  description: null,
  label: null,
  componentKind: null,
  field: "CHEMISTRY",
  subjectName: "Kutch Ajrakh",
  craftSlug: "Kutch-Ajrakh",
  createdAt: "2026-11-19T10:00:00Z",
  reasons: [],
  gates: [{ gate: "QUOTES", passed: true, reasons: [] }]
};

const TASK: OpenTask = {
  key: "THIN_FIELD:craft:Kutch-Ajrakh:HISTORY",
  kind: "THIN_FIELD",
  priority: "HIGH",
  subject: { kind: "craft", slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", pageUrl: "https://kalavigyan.example/crafts/Kutch-Ajrakh" },
  field: "HISTORY",
  need: null,
  needed: "Four more history facts",
  acceptance: "Each fact quoted from its source",
  count: 4,
  factIds: [],
  sourceIds: [],
  prompt: "research_field",
  reservedUntil: null
};

test("a fact names its craft, its field, one sentence and a source with the words that state it", () => {
  expect(factProblems(emptyFact())).toEqual([
    "Choose the craft the fact is about.",
    "Choose the field the fact belongs to.",
    "Write the fact in at least 20 characters.",
    "Source 1: give its https address.",
    "Source 1: give its title.",
    "Source 1: copy the words that state the fact."
  ]);
  expect(factProblems(DRAFT)).toEqual([]);
});

test("a source is named once, takes an https address and quotes of 20 to 300 characters given once", () => {
  const source = DRAFT.sources[0];
  const twice: FactDraft = { ...DRAFT, sources: [source, { ...source, url: "https://example.org/madder" }] };
  expect(factProblems(twice)).toEqual(["Name each source once and give all its quotes under it."]);
  const bad = { ...source, url: "http://example.org", quotes: [{ text: "too short", locator: "" }, { text: "x".repeat(301), locator: "" }] };
  expect(factProblems({ ...DRAFT, sources: [bad] })).toEqual([
    "Source 1: give its https address.",
    "Source 1: each quote is at least 20 characters.",
    "Source 1: each quote is at most 300 characters."
  ]);
  const repeated = { ...source, quotes: [{ text: QUOTE, locator: "" }, { text: ` ${QUOTE}`, locator: "p. 2" }] };
  expect(factProblems({ ...DRAFT, sources: [repeated] })).toEqual(["Source 1: give each quote once."]);
});

test("a fact category subject asks for the category, and further fields leave out the main one", () => {
  const category: FactDraft = { ...DRAFT, subjectKind: "category", subjectSlug: "", fields: ["CHEMISTRY"] };
  expect(factProblems(category)).toEqual(["Choose the category the fact is about.", "Choose at most 3 further fields, leaving out the main one."]);
  expect(factProblems({ ...DRAFT, fields: ["HISTORY", "BOTANY", "DESIGN", "POLICY"] })).toEqual(["Choose at most 3 further fields, leaving out the main one."]);
});

test("the fact's body trims every value, sends a blank licence or locator as null and drops empty quotes", () => {
  expect(factBody(DRAFT)).toEqual({
    subject: { kind: "craft", slug: "Kutch-Ajrakh" },
    field: "CHEMISTRY",
    fields: [],
    statement: "Alizarin from madder binds to alum on the cloth as a red lake.",
    sources: [{ url: "https://example.org/madder", title: "Madder dyeing", licence: null, quotes: [{ text: QUOTE, locator: null }] }]
  });
});

test("what the gates said reads as published, waiting or refused", () => {
  const reply: ProposalReply = {
    schemaVersion: 1,
    outcome: "PUBLISHED",
    claimId: ITEM.id,
    status: "APPROVED",
    level: "PROVISIONAL",
    approvedAtOnce: true,
    inReviewQueue: false,
    sourcesDiffer: false,
    differsFrom: [],
    gates: [{ gate: "NOVELTY", passed: true, reasons: ["It adds the lake's colour."] }],
    message: "Published."
  };
  expect(parseShape(proposalReplyShape, reply)).toEqual(reply);
  const placed = { ...reply, readers: { shown: false, reason: "HELD", pageUrl: "https://kalavigyan.example/crafts/Kutch-Ajrakh", chapter: "chem", field: "CHEMISTRY", inProse: false, writeTask: null } };
  expect(parseShape(proposalReplyShape, placed)).toEqual(placed);
  expect(replyHeadline(reply)).toBe("Published and approved");
  expect(replyHeadline({ ...reply, approvedAtOnce: false })).toBe("Published, waiting for a reviewer's check");
  expect(replyHeadline({ ...reply, outcome: "WAITING" })).toBe("Received: it waits for a reviewer");
  expect(replyHeadline({ ...reply, outcome: "REFUSED" })).toBe("Not added");
  expect(() => parseShape(proposalReplyShape, { ...reply, gates: [{ gate: "MOOD", passed: true, reasons: [] }] })).toThrow();
});

test("an open task starts a fact on its craft and field, and a family task starts nothing", () => {
  const started = factFromTask({ ...emptyFact(), fields: ["HISTORY", "BOTANY"] }, TASK);
  expect([started.subjectKind, started.subjectSlug, started.subjectName, started.field, started.fields]).toEqual(["craft", "Kutch-Ajrakh", "Kutch Ajrakh", "HISTORY", ["BOTANY"]]);
  const family = { ...TASK, subject: { ...TASK.subject!, kind: "family" as const } };
  expect(factFromTask(DRAFT, family)).toBe(DRAFT);
});

test("open work offers at most five starts of the page's task kinds and subjects", () => {
  const many = Array.from({ length: 7 }, (_, index) => ({ ...TASK, key: `THIN_FIELD:craft:c${index}:HISTORY` }));
  const others = [{ ...TASK, kind: "PAGE_FORM" as const }, { ...TASK, subject: null }, { ...TASK, subject: { ...TASK.subject!, kind: "family" as const } }];
  const starts = startingTasks([...others, ...many], ["THIN_FIELD"], ["craft"]);
  expect(starts.map((task) => task.key)).toEqual(["c0", "c1", "c2", "c3", "c4"].map((slug) => `THIN_FIELD:craft:${slug}:HISTORY`));
  expect(openWorkFilter(["MISSING_COMPONENT"])).toEqual({ kind: "MISSING_COMPONENT" });
  expect(openWorkFilter(["MISSING_FIELD", "THIN_FIELD"])).toEqual({});
});

test("only a waiting contribution can be withdrawn, because a published one stays published", () => {
  expect(canWithdraw(ITEM)).toBe(true);
  for (const state of ["PUBLISHED", "APPROVED", "REFUSED", "REJECTED", "WITHDRAWN", "RETIRED"] as const) {
    expect(canWithdraw({ ...ITEM, state })).toBe(false);
  }
  expect(withdrawPath(ITEM)).toBe("/contributions/proposals/facts/0b7c4a52-3c0e-4d43-9a3f-111111111111/withdraw");
  expect(withdrawPath({ ...ITEM, kind: "COMPONENT" })).toBe("/contributions/proposals/components/0b7c4a52-3c0e-4d43-9a3f-111111111111/withdraw");
});

test("each state has its own words, and a published fact says whether a reviewer has checked it", () => {
  expect(stateLabel(ITEM)).toBe("Waiting for review");
  expect(stateLabel({ ...ITEM, state: "PUBLISHED", status: "IN_REVIEW" })).toBe("Published, waiting for a reviewer's check");
  expect(stateLabel({ ...ITEM, state: "PUBLISHED", status: "APPROVED" })).toBe("Published");
  expect(stateLabel({ ...ITEM, state: "REFUSED", status: "REJECTED" })).toBe("Not added: the checks refused it");
  expect(stateLabel({ ...ITEM, state: "REJECTED", status: "REJECTED" })).toBe("Not added: a reviewer rejected it");
  expect(stateLabel({ ...ITEM, kind: "COMPONENT", state: "APPROVED", status: "APPROVED" })).toBe("Approved, waiting to be built");
});

test("the server's own proposals parse, and each page lists its own kind", () => {
  expect(parseShape(ownProposalShape, ITEM)).toEqual(ITEM);
  expect(() => parseShape(ownProposalShape, { ...ITEM, state: "HIDDEN" })).toThrow();
  const component: OwnProposal = { ...ITEM, id: "c", kind: "COMPONENT", componentKind: "molecule_3d" };
  expect(itemsOfKind([ITEM, component], "COMPONENT")).toEqual([component]);
  expect(kindLabel("molecule_3d")).toBe("Molecule 3d");
  expect(kindLabel("what_if")).toBe("What if");
});

test("the terms are asked for until they are accepted or ticked", () => {
  const terms = { version: "2026-11-19", acceptedAt: null };
  expect(withTerms(["Give it a title."], terms, false)).toEqual(["Give it a title.", "Accept the contribution terms, version 2026-11-19, to send it."]);
  expect(withTerms([], terms, true)).toEqual([]);
  expect(withTerms([], { ...terms, acceptedAt: "2026-11-19T09:00:00Z" }, false)).toEqual([]);
  expect(withTerms([], null, true)).toEqual(["The contribution terms could not be read. Reload the page."]);
});

test("list edits replace or remove one entry and keep the rest in order", () => {
  expect(replaced(["a", "b", "c"], 1, "B")).toEqual(["a", "B", "c"]);
  expect(removed(["a", "b", "c"], 0)).toEqual(["b", "c"]);
});

test("the fact and component pages are guarded by the capability the API requires, with one nav entry", () => {
  const gates = Object.fromEntries(ROUTE_GUARDS.map((guard) => [guard.path, guard.gate]));
  expect(gates["/contributions/facts"]).toBe("require(PROPOSE_KNOWLEDGE)");
  expect(gates["/contributions/components"]).toBe("require(PROPOSE_KNOWLEDGE)");
  const researcher: User = { id: "r", email: "r@example.org", name: "R", role: "RESEARCHER", capabilities: ["PROPOSE_KNOWLEDGE"] };
  const student: User = { id: "s", email: "s@example.org", name: "S", role: "STUDENT", capabilities: [] };
  expect([canAccessRoute(researcher, "/contributions/components"), canAccessRoute(student, "/contributions/facts")]).toEqual([true, false]);
  const entries = NAV_ITEMS.filter((item) => item.href.startsWith("/contributions/") && item.href !== "/contributions/pictures");
  expect(entries.map((item) => [item.href, item.gate])).toEqual([["/contributions/facts", "require(PROPOSE_KNOWLEDGE)"]]);
});
