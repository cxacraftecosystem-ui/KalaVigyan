import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { COMPONENT_VIEWS } from "../components/monograph/componentViews";
import { VIEWS as DATA_VIEWS } from "../components/monograph/kinds/data";
import { isDeclared } from "../lib/componentSpecsGeneral";
import type { ComponentView } from "../lib/componentViewContract";
import { kinMaterial, sharesLine } from "../lib/kinCraftsSpec";
import type { MonographComponent } from "../lib/monographDocument";

const LABEL = "bagh-print/kin/related-crafts";
const KIN = {
  head: { title: "Crafts of the same family", family: "Textiles · Hand block printing" },
  crafts: [
    { name: "Bagru Hand Block Print", path: "/crafts/Bagru-Hand-Block-Print", place: "Rajasthan", gi: true, monograph: true, shares: ["Alum", "Harda"], sentence: "kin-1" },
    { name: "Sanganeri Print", path: "/crafts/Sanganeri-Print", place: null, gi: false, monograph: false, shares: [], sentence: "kin-2" }
  ]
};

function component(): MonographComponent {
  return { label: LABEL, chapter: "kin", anchor: "#bagh-print--kin--related-crafts", kind: "related_crafts", title: "Crafts of the same family", description: "Kin crafts.", field: "OVERVIEW", fields: ["OVERVIEW"], subjects: ["craft:Bagh-Print"] };
}

function drawn(spec: object): string {
  const view = COMPONENT_VIEWS.related_crafts as ComponentView;
  const props = { component: component(), spec: spec as Record<string, unknown>, unitRefs: [], renderUnit: (ref: string) => `[${ref}]`, renderComponent: () => null };
  return renderToStaticMarkup(createElement(() => view(props)));
}

test("a generated page's kin crafts are the declared form of related_crafts, and Kutch Ajrakh's authored form keeps its own view", () => {
  expect(isDeclared(KIN)).toBe(true);
  expect(DATA_VIEWS.related_crafts).toBeDefined();
  expect(COMPONENT_VIEWS.related_crafts).not.toBe(DATA_VIEWS.related_crafts);
  expect(drawn(KIN)).toContain('data-testid="kin-crafts"');
});

test("each kin craft shows its family swatch, its link, its place and tags, the materials it shares and its cited sentence", () => {
  const html = drawn(KIN);
  expect(html.match(/data-testid="kin-craft"/g)).toHaveLength(2);
  expect(html.match(/data-testid="family-swatch"/g)).toHaveLength(2);
  expect(html).toContain("g-textile");
  expect(html).toContain('href="/crafts/Bagru-Hand-Block-Print"');
  expect(html).toContain("Shares Alum and Harda");
  expect(html).toContain("[kin-1]");
  expect(html).toContain("[kin-2]");
  expect(html).toContain('<span class="sr-only"> registered</span>');
  expect(html).toContain('id="bagh-print--kin--related-crafts-title"');
  expect(html).not.toMatch(/Shares <\/span>|Shares $/);
});

test("the swatch is the family's plate ground and a craft sharing nothing names no share", () => {
  expect(kinMaterial("Textiles · Hand block printing")).toBe("textile");
  expect(kinMaterial("Clay · Figurines and toys")).toBe("toys");
  expect(kinMaterial(null)).toBe("misc");
  expect(sharesLine([])).toBeNull();
  expect(sharesLine(["Alum"])).toBe("Shares Alum");
  expect(sharesLine(["Alum", "Harda", "Indigo"])).toBe("Shares Alum, Harda and Indigo");
  expect(drawn({ ...KIN, crafts: [] })).toBe("");
});
