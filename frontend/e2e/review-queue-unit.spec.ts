import { expect, test } from "@playwright/test";

import { NAV_ITEMS, isNavItemVisible } from "@/components/DynamicIslandNav";
import { canAccessRoute } from "@/lib/permissions";
import { decisionBody, DECISION_PATH, queueQuery, reviewQueuePageShape, testimonyDecisionBody, testimonyNoteReady, type QueueItem, type ReviewQueuePage } from "@/lib/reviewQueueContract";
import {
  factActions,
  fieldsLine,
  filingOf,
  filtersFromSearch,
  filtersSearch,
  gateLine,
  heldLine,
  isFiltered,
  kindTabs,
  overlapLine,
  proposerLine,
  reasonProblem,
  withNextPage,
  withoutItem
} from "@/lib/reviewQueueView";
import { parseShape } from "@/lib/shape";
import type { User, UserRole } from "@/lib/types";

const CRAFT = { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" };

const FACT = {
  id: "00000000-0000-4000-8000-000000000001",
  origin: "AGENT",
  submittedAt: "2026-11-19T11:50:00Z",
  craft: CRAFT,
  proposer: { name: "Meera Contributor", role: "RESEARCHER" },
  kind: "FACTS",
  fact: {
    statement: "An indigo vat turns blue at its surface.",
    field: "CHEMISTRY",
    fields: ["PROCESS"],
    status: "DRAFT",
    level: "PROVISIONAL",
    sourcesDiffer: true,
    concept: { name: "Indigo", type: "MATERIAL" },
    sources: [{ title: "Indigo vats", url: null, licence: "CC-BY-4.0", reliability: "B", quotes: [{ text: "the vat is yellow-green", locator: "p. 4" }] }],
    gates: [{ gate: "DUPLICATE", passed: true, reasons: ["duplicate passed"], model: null, related: [{ id: "held", text: "A reduced vat is yellow-green." }] }]
  }
};

const PROPOSAL = {
  id: "00000000-0000-4000-8000-000000000002",
  origin: "AGENT",
  submittedAt: "2026-11-19T11:40:00Z",
  craft: null,
  proposer: null,
  kind: "COMPONENTS",
  component: {
    label: "kutch-ajrakh/chemistry/vat-surface",
    title: "Indigo vat surface",
    description: "Shows the blue film forming where the vat meets the air.",
    kind: "molecule_3d",
    field: "CHEMISTRY",
    fields: [],
    subjects: [{ kind: "CRAFT", key: "Kutch-Ajrakh" }],
    consideredLabels: ["shared/chemistry/indigo-reduction"],
    extends: null,
    extension: null,
    taskKey: null,
    closest: [
      {
        component: { label: "shared/chemistry/alum", title: "Alum", description: "Alum binds.", kind: "molecule_3d", field: "CHEMISTRY", fields: [], craftSlug: null, subjects: [] },
        overlap: 0.077,
        reasons: ["it already has this label"]
      }
    ]
  }
};

const WITHDRAWN = {
  id: "00000000-0000-4000-8000-000000000003",
  origin: "TESTIMONY",
  submittedAt: "2026-11-19T11:30:00Z",
  craft: CRAFT,
  proposer: null,
  kind: "TESTIMONY",
  testimony: { id: "00000000-0000-4000-8000-000000000003", status: "WITHDRAWN", craft: CRAFT, withdrawnAt: null }
};

const PAGE = {
  schemaVersion: 1,
  kinds: ["FACTS", "TESTIMONY", "IMAGES", "COMPONENTS"],
  counts: { FACTS: 3, TESTIMONY: 1, IMAGES: 0, COMPONENTS: 1 },
  total: 5,
  items: [FACT, PROPOSAL, WITHDRAWN],
  nextCursor: "1795089600000000~00000000000000000000000000000003"
};

function parsed(): ReviewQueuePage {
  return parseShape(reviewQueuePageShape, PAGE);
}

function person(role: UserRole): User {
  return { id: role, email: `${role.toLowerCase()}@example.org`, name: role, role };
}

test("a queue page from the server is read item by item, whatever its kind", () => {
  const page = parsed();
  expect(page.items.map((item) => item.kind)).toEqual(["FACTS", "COMPONENTS", "TESTIMONY"]);
  const fact = page.items[0] as Extract<QueueItem, { kind: "FACTS" }>;
  expect(fact.fact.sources[0].quotes[0]).toEqual({ text: "the vat is yellow-green", locator: "p. 4" });
  expect(() => parseShape(reviewQueuePageShape, { ...PAGE, items: [{ ...FACT, kind: "PAGES" }] })).toThrow();
  expect(() => parseShape(reviewQueuePageShape, { ...PAGE, items: [{ ...FACT, email: "x@example.org" }] })).toThrow();
});

test("the query names only the filters that are set, then the page size", () => {
  expect(queueQuery({ kind: null, craft: null, origin: null }, null)).toBe("limit=25");
  expect(queueQuery({ kind: "FACTS", craft: "Kutch-Ajrakh", origin: "AGENT" }, "5~ab", 10)).toBe("kind=FACTS&craft=Kutch-Ajrakh&origin=AGENT&cursor=5%7Eab&limit=10");
});

test("each decision goes to its own route with a reason or a note", () => {
  expect(DECISION_PATH("FACTS", "a/b", "raise")).toBe("/review-queue/FACTS/a%2Fb/raise");
  expect(decisionBody("reject", "  Misquoted.  ")).toEqual({ reason: "Misquoted." });
  expect(decisionBody("retract", "Wrong vat.")).toEqual({ reason: "Wrong vat." });
  expect(decisionBody("approve", "   ")).toEqual({ note: null });
  expect(decisionBody("raise", "Checked.")).toEqual({ note: "Checked." });
});

test("pictures and testimony are decided through the queue's route, testimony with its version and reason", () => {
  expect(DECISION_PATH("IMAGES", "p1", "reject")).toBe("/review-queue/IMAGES/p1/reject");
  expect(DECISION_PATH("TESTIMONY", "t1", "approve")).toBe("/review-queue/TESTIMONY/t1/approve");
  expect(testimonyDecisionBody({ version: 4 }, { action: "approve", englishChecked: true })).toEqual({ version: 4, englishChecked: true });
  expect(testimonyDecisionBody({ version: 4 }, { action: "reject", reason: "MISHEARD", note: "   " })).toEqual({ version: 4, testimonyReason: "MISHEARD", reason: null });
  expect(testimonyDecisionBody({ version: 4 }, { action: "reject", reason: "OTHER", note: " Off topic. " })).toEqual({ version: 4, testimonyReason: "OTHER", reason: "Off topic." });
  expect([testimonyNoteReady("", ""), testimonyNoteReady("MISHEARD", ""), testimonyNoteReady("OTHER", ""), testimonyNoteReady("OTHER", "ok"), testimonyNoteReady("OTHER", "Off topic.")]).toEqual([false, true, false, false, true]);
  expect(testimonyNoteReady("UNCLEAR", "x".repeat(501))).toBe(false);
});

test("a waiting fact is rejected and a live one retracted, and only a reason lets either through", () => {
  expect(factActions("DRAFT")).toEqual(["approve", "raise", "reject"]);
  expect(factActions("IN_REVIEW")).toEqual(["approve", "raise", "retract"]);
  expect(factActions("APPROVED")).toEqual([]);
  expect(reasonProblem("reject", " no ")).toBe("Give the reason, in at least 3 characters.");
  expect(reasonProblem("retract", "abc")).toBeNull();
  expect(reasonProblem("approve", "")).toBeNull();
  expect(reasonProblem("approve", "x".repeat(501))).toBe("Keep it to 500 characters.");
});

test("the filters are read from and written to the address in one order", () => {
  const filters = filtersFromSearch(new URLSearchParams("origin=SITE&kind=IMAGES&craft=%20Kutch-Ajrakh%20"));
  expect(filters).toEqual({ kind: "IMAGES", craft: "Kutch-Ajrakh", origin: null });
  expect(filtersSearch({ ...filters, origin: "CONTRIBUTION" })).toBe("kind=IMAGES&origin=CONTRIBUTION&craft=Kutch-Ajrakh");
  expect(isFiltered({ kind: null, craft: null, origin: null })).toBe(false);
  expect(isFiltered(filters)).toBe(true);
});

test("the tabs count what waits in each kind the reviewer decides", () => {
  expect(kindTabs(parsed()).map((tab) => tab.label)).toEqual(["All (5)", "Facts (3)", "Testimony (1)", "Pictures (0)", "Components (1)"]);
});

test("a decided item leaves the page and its count, and a further page adds only new items", () => {
  const page = parsed();
  const left = withoutItem(page, page.items[1]);
  expect([left.items.length, left.counts.COMPONENTS, left.total]).toEqual([2, 0, 4]);
  expect(withoutItem(left, page.items[1])).toBe(left);
  const next = { ...page, items: [page.items[2], page.items[1]], nextCursor: null };
  const joined = withNextPage(left, next);
  expect([joined.items.map((item) => item.id), joined.nextCursor]).toEqual([[FACT.id, WITHDRAWN.id, PROPOSAL.id], null]);
});

test("the card lines say the fields, the checks, the overlap and who proposed", () => {
  expect(fieldsLine("CHEMISTRY", ["PROCESS", "MATERIALS"])).toBe("Chemistry, also Process, Materials");
  expect(fieldsLine(null, [])).toBeNull();
  expect(gateLine({ gate: "QUOTES", passed: false, reasons: [], model: null, related: [] })).toBe("Quotes found in the source: refused");
  expect(overlapLine(0.077)).toBe("8 per cent of words shared");
  expect(proposerLine({ name: "Meera Contributor", role: "RESEARCHER" })).toBe("Proposed by Meera Contributor, Researcher");
  expect(proposerLine(null)).toBeNull();
});

test("Professors and above open the review page, and the admin menu points to it", () => {
  expect((["RESEARCHER", "PROFESSOR", "ADMIN", "MASTER_ADMIN"] as const).map((role) => canAccessRoute(person(role), "/admin/review"))).toEqual([false, true, true, true]);
  const review = NAV_ITEMS.find((item) => item.href === "/admin/review");
  expect(review && isNavItemVisible(review, person("ADMIN"), true)).toBe(true);
  expect(review && isNavItemVisible(review, person("RESEARCHER"), true)).toBe(false);
});

test("a held write-back is read with its reason, and a page without the field still reads", () => {
  const held = { reason: "names Afghanistan but no craft of it", suggestedCraft: "Ajanta-Painting" };
  const withHeld = parseShape(reviewQueuePageShape, { ...PAGE, items: [{ ...FACT, fact: { ...FACT.fact, held } }] });
  const fact = withHeld.items[0] as Extract<QueueItem, { kind: "FACTS" }>;
  expect(fact.fact.held).toEqual(held);
  expect(heldLine(held)).toBe("Held for a reviewer: it names Afghanistan but no craft of it.");
  const unheld = parseShape(reviewQueuePageShape, { ...PAGE, items: [{ ...FACT, fact: { ...FACT.fact, held: null } }] });
  expect((unheld.items[0] as Extract<QueueItem, { kind: "FACTS" }>).fact.held).toBeNull();
  expect((parsed().items[0] as Extract<QueueItem, { kind: "FACTS" }>).fact.held).toBeUndefined();
  expect(() => parseShape(reviewQueuePageShape, { ...PAGE, items: [{ ...FACT, fact: { ...FACT.fact, held: { reason: "x" } } }] })).toThrow();
});

test("an approval files the fact under the craft or family the reviewer chose, and only an approval", () => {
  expect(filingOf("craft:Khurja-Pottery")).toEqual({ craft: "Khurja-Pottery" });
  expect(filingOf("family:Mud-Based-Craft-Category")).toEqual({ family: "Mud-Based-Craft-Category" });
  expect(filingOf("")).toBeNull();
  expect(decisionBody("approve", "Names Khurja.", { craft: "Khurja-Pottery" })).toEqual({ note: "Names Khurja.", craft: "Khurja-Pottery" });
  expect(decisionBody("approve", "", { family: "Mud-Based-Craft-Category" })).toEqual({ note: null, family: "Mud-Based-Craft-Category" });
  expect(decisionBody("reject", "Off topic.", { craft: "Khurja-Pottery" })).toEqual({ reason: "Off topic." });
  expect(decisionBody("raise", "Checked.", { craft: "Khurja-Pottery" })).toEqual({ note: "Checked." });
});
