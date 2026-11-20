import { expect, test } from "@playwright/test";

import { reviewQueuePageShape, type QueueItem } from "@/lib/reviewQueueContract";
import { deliveredFactLine, factNumbersLine } from "@/lib/reviewQueueView";
import { parseShape } from "@/lib/shape";

const FACT_ID = "00000000-0000-4000-8000-0000000000f1";
const OTHER_ID = "00000000-0000-4000-8000-0000000000f2";
const DELIVERY = {
  drawing: null,
  units: [
    { unit: "u0001", text: "Alum fixes the madder red on the cotton.", claimIds: [FACT_ID] },
    { unit: "u0003", text: "Mordant", claimIds: [] }
  ],
  facts: [
    {
      id: FACT_ID,
      text: "Alum fixes the madder red on the cotton.",
      level: "PROVISIONAL",
      shown: true,
      sources: [{ title: "Mordants", url: "https://example.org/mordants", licence: null, reliability: "B", quotes: [{ text: "alum fixes the red", locator: "p. 2" }] }]
    }
  ]
};
const COMPONENT = {
  id: "00000000-0000-4000-8000-0000000000c1",
  origin: "AGENT",
  submittedAt: "2026-11-20T10:00:00Z",
  craft: { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" },
  proposer: null,
  kind: "COMPONENTS",
  component: {
    label: "kutch-ajrakh/chemistry/alum-table",
    title: "Alum on cotton",
    description: "A table of what alum does to the madder red on cotton.",
    kind: "general_table",
    field: "CHEMISTRY",
    fields: [],
    subjects: [{ kind: "CRAFT", key: "Kutch-Ajrakh" }],
    consideredLabels: [],
    extends: null,
    extension: null,
    taskKey: null,
    closest: [],
    delivery: DELIVERY
  }
};

function page(item: unknown) {
  return { schemaVersion: 1, kinds: ["COMPONENTS"], counts: { COMPONENTS: 1 }, total: 1, items: [item], nextCursor: null };
}

test("a component item carries its delivered units and the facts they rest on", () => {
  const parsed = parseShape(reviewQueuePageShape, page(COMPONENT));
  const item = parsed.items[0] as Extract<QueueItem, { kind: "COMPONENTS" }>;
  expect(item.component.delivery?.units.map((unit) => unit.unit)).toEqual(["u0001", "u0003"]);
  expect(item.component.delivery?.facts[0].sources[0].quotes[0].text).toBe("alum fixes the red");
  const older = { ...COMPONENT, component: { ...COMPONENT.component, delivery: undefined } };
  expect((parseShape(reviewQueuePageShape, page(older)).items[0] as typeof item).component.delivery).toBeUndefined();
  const broken = { ...COMPONENT, component: { ...COMPONENT.component, delivery: { ...DELIVERY, facts: undefined } } };
  expect(() => parseShape(reviewQueuePageShape, page(broken))).toThrow();
});

test("each unit names the numbered facts it rests on, and a label rests on none", () => {
  const numbers = new Map([
    [FACT_ID, 1],
    [OTHER_ID, 2]
  ]);
  expect(factNumbersLine([FACT_ID], numbers)).toBe("Rests on fact 1");
  expect(factNumbersLine([OTHER_ID, FACT_ID, OTHER_ID], numbers)).toBe("Rests on facts 1, 2");
  expect(factNumbersLine([], numbers)).toBe("A heading or label, resting on no fact");
});

test("each fact says its number, its level and whether the page shows it", () => {
  const fact = { ...DELIVERY.facts[0], level: "PROVISIONAL" as const };
  expect(deliveredFactLine(1, fact)).toBe("Fact 1 · Provisional · shown on the page");
  expect(deliveredFactLine(2, { ...fact, level: null, shown: false })).toBe("Fact 2 · held from the page");
});
