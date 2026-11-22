import { expect, test } from "@playwright/test";

import { renderChemistry } from "@/lib/chemistry";
import { pubchemHref, reactionSpoken, speciesNamesLine, speciesSides, STAGE_TYPE_LABEL, type SpeciesTerm } from "@/lib/processView";
import { ShapeError } from "@/lib/shape";

const IRON: SpeciesTerm[] = [
  { role: "REACTANT", formula: "Fe", name: "Iron", coefficient: 1 },
  { role: "REACTANT", formula: "CH3COOH", name: "Acetic acid", coefficient: 2 },
  { role: "PRODUCT", formula: "Fe(CH3COO)2", name: "Iron(II) acetate", coefficient: 1 },
  { role: "PRODUCT", formula: "H2", name: "Hydrogen", coefficient: 1 }
];
const LAKE: SpeciesTerm[] = [
  { role: "REACTANT", formula: "Al^3+", name: "Aluminium from the alum mordant", coefficient: null },
  { role: "REACTANT", formula: "C14H8O4", name: "Alizarin", coefficient: null },
  { role: "PRODUCT", formula: null, name: "Aluminium-alizarin lake", coefficient: null }
];

test("a balanced reaction reads as names with its coefficients", () => {
  expect(reactionSpoken({ species: IRON, balanced: true })).toBe("Iron + 2 Acetic acid gives Iron(II) acetate + Hydrogen");
  expect(speciesNamesLine({ species: IRON })).toBe("Iron · Acetic acid → Iron(II) acetate · Hydrogen");
});

test("an unbalanced reaction reads its names without coefficients", () => {
  expect(reactionSpoken({ species: IRON, balanced: false })).toBe("Iron + Acetic acid gives Iron(II) acetate + Hydrogen");
});

test("a species-only reaction reads as its names", () => {
  expect(reactionSpoken({ species: LAKE, balanced: false })).toBe("Aluminium from the alum mordant + Alizarin gives Aluminium-alizarin lake");
  expect(speciesSides({ species: LAKE }).products.map((species) => species.name)).toEqual(["Aluminium-alizarin lake"]);
});

test("a species with neither a name nor a formula is refused", () => {
  expect(() => speciesNamesLine({ species: [{ role: "REACTANT", formula: null, name: null, coefficient: null }] })).toThrow(ShapeError);
});

test("a stage type reads as its English label", () => {
  expect([STAGE_TYPE_LABEL.PRINT, STAGE_TYPE_LABEL.MORDANT, STAGE_TYPE_LABEL.DYE]).toEqual(["Printing", "Mordanting", "Dyeing"]);
});

test("PubChem links only for a real compound id", () => {
  expect(pubchemHref(6342)).toBe("https://pubchem.ncbi.nlm.nih.gov/compound/6342");
  expect(pubchemHref(null)).toBeNull();
  expect(pubchemHref(0)).toBeNull();
});

test("every formula a reaction names renders through mhchem", () => {
  const sources = ["Fe + 2 CH3COOH -> Fe(CH3COO)2 + H2", ...[...IRON, ...LAKE].flatMap((species) => (species.formula ? [species.formula] : []))];
  for (const source of sources) {
    const html = renderChemistry(source, false);
    expect(html, source).toContain("katex");
    expect(html, source).not.toContain("katex-error");
  }
});
