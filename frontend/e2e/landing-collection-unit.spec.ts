import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { categoriesHeading, monographLine } from "@/components/landing/CategoriesSection";
import { collectionDek } from "@/components/landing/CollectionSection";
import { batches, COVERAGE_BATCH, coveragePath } from "@/components/landing/fieldCoverageServer";
import { FIELD_CHAPTER, fieldHoldings, fieldsFinding } from "@/components/landing/fieldHoldings";
import { FieldsSection, fieldsDek, leadLine } from "@/components/landing/FieldsSection";
import { collectionStats, documentPlates, familyBlocks, interleaved, landingCollection } from "@/components/landing/landingCollection";
import { parseCraftCatalogue } from "@/lib/craftCatalogueContract";
import { DISCIPLINES, type Discipline } from "@/lib/explainerBlockBase";
import type { FieldCoverage } from "@/lib/fieldCoverage";

import { FRONTEND } from "./moduleGraph";

const CATALOGUE = parseCraftCatalogue(JSON.parse(readFileSync(join(FRONTEND, "..", "shared", "craft.catalogue.golden.json"), "utf8")));

function coverage(slug: string, name: string, claims: Partial<Record<Discipline, number>>): FieldCoverage {
  const fields = DISCIPLINES.map((field) => {
    const count = claims[field] ?? 0;
    return { field, claims: count, structureClaims: 0, sources: count, sections: count > 0 ? 1 : 0, sentences: count, figures: 0, standing: count >= 3 ? ("COVERED" as const) : count > 0 ? ("THIN" as const) : ("MISSING" as const) };
  });
  return { schemaVersion: 1, subjectKind: "craft", subjectSlug: slug, name, claimsMin: 3, claims: 0, sources: 0, covered: [], thin: [], missing: [], fields };
}

const ALL_SIXTEEN = Object.fromEntries(DISCIPLINES.map((field) => [field, 2])) as Record<Discipline, number>;
const COVERAGES = [
  coverage("Kutch-Ajrakh", "Kutch Ajrakh", { ...ALL_SIXTEEN, CHEMISTRY: 38, BOTANY: 0 }),
  coverage("Bastar-Dhokra", "Bastar Dhokra", { ...ALL_SIXTEEN, CHEMISTRY: 12, PHYSICS: 0, BOTANY: 0 }),
  coverage("Agra-Marble-Inlay", "Agra Marble Inlay", { ...ALL_SIXTEEN, GEOLOGY: 16, BOTANY: 0, PHYSICS: 0 })
];

test("each field counts the monographs holding cited facts in it and names the one holding the most", () => {
  const holdings = fieldHoldings(COVERAGES);
  expect(holdings.monographs).toBe(3);
  expect(holdings.fields.map((field) => field.field)).toEqual([...DISCIPLINES]);
  const byField = new Map(holdings.fields.map((field) => [field.field, field]));
  expect(byField.get("CHEMISTRY")?.crafts).toBe(3);
  expect(byField.get("CHEMISTRY")?.lead).toEqual({ slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", facts: 38, href: "/crafts/Kutch-Ajrakh#chem" });
  expect(byField.get("GEOLOGY")?.lead?.href).toBe("/crafts/Agra-Marble-Inlay#why");
  expect(byField.get("PHYSICS")?.crafts).toBe(1);
  expect(byField.get("BOTANY")).toEqual({ field: "BOTANY", label: "Botany", crafts: 0, lead: null });
  expect(byField.get("GEOGRAPHY")?.label).toBe("Geography and water");
  expect(byField.get("PROCESS")?.lead?.name).toBe("Agra Marble Inlay");
  expect(fieldsFinding(holdings)).toBe("All 3 monographs hold cited facts in 14 of the 16 fields; physics is in 1, the fewest.");
  expect(fieldsFinding(fieldHoldings([]))).toBeNull();
  expect(leadLine(byField.get("CHEMISTRY")!)).toBe("38 cited facts");
});

test("a field opens at the chapter the backend files it under", () => {
  const source = readFileSync(join(FRONTEND, "..", "backend", "app", "research", "coverage_chapters.py"), "utf8");
  const filed = Object.fromEntries([...source.matchAll(/"([A-Z]+)": "([a-z]+)"/g)].map((found) => [found[1], found[2]]));
  expect(FIELD_CHAPTER).toEqual(filed);
  expect(Object.keys(filed)).toHaveLength(16);
  expect(coveragePath("Kutch-Ajrakh")).toBe("/crafts/Kutch-Ajrakh/coverage");
  expect(batches([1, 2, 3, 4, 5, 6, 7], 3)).toEqual([[1, 2, 3], [4, 5, 6], [7]]);
  expect(COVERAGE_BATCH).toBeLessThanOrEqual(8);
});

test("the fields section draws sixteen rows from coverage, and the sixteen names when coverage cannot be read", () => {
  const holdings = fieldHoldings(COVERAGES);
  const markup = renderToStaticMarkup(createElement(FieldsSection, { holdings }));
  expect(markup.match(/data-testid="landing-field"/g)).toHaveLength(16);
  expect(markup).toContain('href="/crafts/Kutch-Ajrakh#chem"');
  expect(markup).toContain(fieldsDek(holdings));
  expect(markup).toContain(">Sixteen fields</h2>");
  const plain = renderToStaticMarkup(createElement(FieldsSection, { holdings: null }));
  expect(plain.match(/<li/g)).toHaveLength(16);
  for (const label of ["Overview", "Physics", "Geology and soil", "Ecology", "Health", "Society", "Policy"]) expect(plain).toContain(`>${label}</li>`);
  expect(plain.replace(/<[^>]+>/g, " ")).not.toMatch(/no data|coming soon|not yet/i);
});

test("the collection shows the monographs across families, the families with plates of their crafts, and true counts", () => {
  expect(interleaved([[1, 2, 3], [4], [5, 6]])).toEqual([1, 4, 5, 2, 6, 3]);
  expect(documentPlates(CATALOGUE).map((plate) => plate.craft.slug)).toEqual(["Kutch-Ajrakh", "Bastar-Dhokra"]);
  expect(documentPlates(CATALOGUE)[0].craft.aliases).toEqual([]);
  const families = familyBlocks(CATALOGUE);
  expect(families.map((family) => [family.name, family.href, family.count, family.documents, family.plates.map((plate) => plate.craft.slug)])).toEqual([
    ["Textiles", "/categories/Textiles-Based-Craft-Category", 4, 1, ["Bagru-Hand-Block-Print", "Phulkari"]],
    ["Metal", "/categories/Metal-Craft-Category", 3, 1, ["Brass-And-Bell-Metal-Craft", "Metal-Embosing"]]
  ]);
  expect(collectionStats(CATALOGUE).map((stat) => [stat.key, stat.value])).toEqual([
    ["crafts", 7],
    ["families", 2],
    ["states", 6],
    ["gi", 5],
    ["monographs", 2]
  ]);
  const collection = landingCollection(CATALOGUE);
  expect(collection && collectionDek(collection)).toBe(
    "7 crafts in two families, from 6 states and union territories. Every page is open to read: each craft has its plate and record, and the monographs are written out in full."
  );
  expect(landingCollection(null)).toBeNull();
  expect([categoriesHeading(9), categoriesHeading(1)]).toEqual(["Nine families of craft", "One family of craft"]);
  expect([monographLine(0), monographLine(1), monographLine(7)]).toEqual([null, "1 monograph read in full", "7 monographs read in full"]);
});
