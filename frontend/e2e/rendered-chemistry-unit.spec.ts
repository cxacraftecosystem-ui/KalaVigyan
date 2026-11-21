import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ChemEquation } from "../components/answer/ChemEquation";
import { RenderedChemistryProvider } from "../components/answer/RenderedChemistry";
import { chemistryAsks, chemistryKey, documentChemistry } from "../lib/chemistryKeys";
import type { MonographDocument } from "../lib/monographDocument";
import { renderedChemistry } from "../lib/server/renderedChemistry";

import { eagerModules } from "./moduleGraph";

const ALUM = "KAl(SO4)2·12H2O";
const REACTION = "Fe + 2 CH3COOH -> Fe(CH3COO)2 + H2";

function documentWith(kind: string, spec: Record<string, unknown>): MonographDocument {
  const component = { label: "a/b/c", chapter: "chem", anchor: "#c", kind, title: "c", description: "", field: "CHEMISTRY", fields: [], subjects: [] };
  return { content: { components: [component] }, specs: { "a/b/c": spec } } as unknown as MonographDocument;
}

test("an answer block's formulas are drawn inline and its equations both ways, each once", () => {
  const spec = { block: { reactions: [{ equation: REACTION, species: [{ formula: ALUM }, { formula: ALUM }] }], formula: ["C", "14"] } };
  expect(chemistryAsks(spec)).toEqual([
    { equation: REACTION, display: true },
    { equation: REACTION, display: false },
    { equation: ALUM, display: false }
  ]);
  expect(documentChemistry(documentWith("answer_block", spec))).toHaveLength(3);
  expect(documentChemistry(documentWith("reaction_player", spec))).toEqual([]);
});

test("the page draws its chemistry on the server and the equation reads it without the typesetter", () => {
  const rendered = renderedChemistry([{ equation: ALUM, display: false }]);
  expect(Object.keys(rendered)).toEqual([chemistryKey(ALUM, false)]);
  expect(rendered[chemistryKey(ALUM, false)]).toContain('class="katex"');
  const html = renderToStaticMarkup(createElement(RenderedChemistryProvider, { rendered }, createElement(ChemEquation, { equation: ALUM, display: false })));
  expect(html).toContain(`aria-label="${ALUM}"`);
  expect(html).toContain('class="katex"');
  expect([...eagerModules("@/components/answer/ChemEquation")]).not.toContain("lib/chemistry.ts");
});

test("an equation the page did not draw shows its text until the typesetter has loaded", () => {
  const html = renderToStaticMarkup(createElement(ChemEquation, { equation: REACTION, label: "iron and vinegar" }));
  expect(html).toContain('role="math"');
  expect(html).toContain('aria-label="iron and vinegar"');
  expect(html).toContain(REACTION.replace(">", "&gt;"));
  expect(html).not.toContain("katex");
});
