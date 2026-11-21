import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { COMPONENT_VIEWS } from "../components/monograph/componentViews";
import { depictedMaterial } from "../lib/componentSpecsPlates";
import { knownColourToken } from "../lib/componentSpecsScienceParts";
import { dipPlayerShape } from "../lib/componentSpecsSciencePlayers";
import type { ComponentView } from "../lib/componentViewContract";
import { DEPICTED_MATERIALS } from "../lib/depictedMaterials";
import { KIND_FIXTURES, type KindFixture } from "../lib/kindFixtures";
import { KIND_PREVIEW_PATH, kindPreviewDocument, renamedRef, renamedSpec } from "../lib/kindPreview";
import type { MonographComponent } from "../lib/monographDocument";
import { parseMonographDocument } from "../lib/monographDocumentShape";
import { parseShape, ShapeError } from "../lib/shape";

const KUTCH = "Kutch-Ajrakh";

function component(fixture: KindFixture): MonographComponent {
  return { label: fixture.label, chapter: "k1", anchor: "#k", kind: fixture.kind, title: fixture.title, description: fixture.description, field: fixture.field, fields: [], subjects: [] };
}

function drawn(fixture: KindFixture): string {
  const view = COMPONENT_VIEWS[fixture.kind] as ComponentView;
  const props = { component: component(fixture), spec: fixture.spec, unitRefs: Object.keys(fixture.units), renderUnit: (ref: string) => fixture.units[ref]?.text ?? "", renderComponent: () => null };
  return renderToStaticMarkup(createElement(() => view(props)));
}

test("twenty-two contributable kinds are each drawn for a craft other than Kutch Ajrakh", () => {
  expect(KIND_FIXTURES).toHaveLength(23);
  expect(new Set(KIND_FIXTURES.map((fixture) => fixture.kind)).size).toBe(22);
  expect(KIND_FIXTURES.filter((fixture) => fixture.craft === KUTCH)).toEqual([]);
  for (const fixture of KIND_FIXTURES) expect(COMPONENT_VIEWS[fixture.kind], fixture.kind).toBeDefined();
});

for (const fixture of KIND_FIXTURES) {
  test(`the ${fixture.kind} view draws ${fixture.label}`, () => {
    const html = drawn(fixture);
    expect(html.length).toBeGreaterThan(0);
    const cited = Object.values(fixture.units).find((unit) => unit.claims.length > 0);
    if (cited) expect(html).toContain(cited.text.replaceAll("'", "&#x27;"));
  });
}

test("the preview page places one of each kind, every unit cited from its craft's sources", () => {
  const document = parseMonographDocument(kindPreviewDocument(KIND_FIXTURES));
  expect(document.pageUrl.endsWith(KIND_PREVIEW_PATH)).toBe(true);
  expect(document.content.components.map((placed) => placed.label).sort()).toEqual(KIND_FIXTURES.map((fixture) => fixture.label).sort());
  expect(Object.keys(document.specs).sort()).toEqual(KIND_FIXTURES.map((fixture) => fixture.label).sort());
  const nested = document.content.layout.filter((entry) => entry.within === "bidriware/chemistry/what-if-lab").map((entry) => entry.ref);
  expect(nested.sort()).toEqual(["bidriware/chemistry/what-blackens", "bidriware/chemistry/why-copper"]);
  const titles = Object.values(document.content.sources).map((source) => source.title);
  expect(new Set(titles).size).toBe(titles.length);
});

test("a fixture's units move to a block of their own and its spec follows them", () => {
  expect(renamedRef(3, "u0012")).toBe("u0312");
  expect(renamedRef(23, "u0099")).toBe("u2399");
  expect(renamedSpec({ title: "u0001", rows: [{ cells: ["u0002", "plain"] }], value: 5 }, { u0001: "u0301", u0002: "u0302" })).toEqual({ title: "u0301", rows: [{ cells: ["u0302", "plain"] }], value: 5 });
});

test("any recorded material can be depicted and no other", () => {
  expect(DEPICTED_MATERIALS).toContain("bidri-black");
  expect(depictedMaterial.parse("cobalt", "dye")).toBe("cobalt");
  expect(() => depictedMaterial.parse("ultramarine", "dye")).toThrow(ShapeError);
  expect(knownColourToken("--dye-field-soil")).toBe(true);
  expect(knownColourToken("--dye-ultramarine")).toBe(false);
  expect(knownColourToken("--ink-1")).toBe(true);
});

test("a dip player names its own phases and may show no equation", () => {
  const dip = KIND_FIXTURES.find((fixture) => fixture.kind === "dip_player");
  const player = parseShape(dipPlayerShape, dip?.spec);
  expect(player.phases.map((phase) => phase.pose)).toEqual(["solution", "lifted", "oiled"]);
  expect(player.equation).toBeUndefined();
  expect(drawn(dip as KindFixture)).not.toContain('class="eq');
});
