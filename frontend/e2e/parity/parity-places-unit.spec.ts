import { expect, test } from "@playwright/test";

import type { SubjectPage } from "./parityBorrowed";
import { locatedCrafts, pageMembers, placeBorrows, strayBorrows, type PlaceFacts } from "./parityPlaces";

const RAINFALL = "shared/climate/kachchh-annual-rainfall-chart";
const KACHCHH = 449;

function page(slug: string, subject: SubjectPage["subject"], labels: Record<string, string[]>, authored = false): SubjectPage {
  const path = subject === "category" ? `/categories/${slug}` : `/crafts/${slug}`;
  return { path, slug, subject, curated: true, authored, components: Object.entries(labels).map(([label, subjects]) => ({ label, kind: "chart", subjects })) };
}

const FACTS: PlaceFacts = {
  located: new Map([[KACHCHH, ["Kutch-Bandhani", "Nizamabad-Black-Pottery"]]]),
  stateOf: new Map([[KACHCHH, "Gujarat"]]),
  practice: new Map([
    ["Kutch-Bandhani", ["Gujarat"]],
    ["Nizamabad-Black-Pottery", ["Uttar Pradesh"]],
    ["Hand-Block-Printing", ["All India"]]
  ]),
  members: new Map([["/categories/Textiles", ["Bagh-Prints", "Kutch-Bandhani"]]])
};

test("a borrowed component naming a district is a place borrow, a page's own or the authored page's is not", () => {
  const pages = [
    page("Nizamabad-Black-Pottery", "craft", { [RAINFALL]: ["place:lgd:449"], "nizamabad-black-pottery/climate/rain": ["place:lgd:123"], "shared/chemistry/alum": ["concept:alum"] }),
    page("Kutch-Ajrakh", "craft", { [RAINFALL]: ["place:lgd:449"] }, true)
  ];
  expect(placeBorrows(pages)).toEqual([{ path: "/crafts/Nizamabad-Black-Pottery", slug: "Nizamabad-Black-Pottery", subject: "craft", label: RAINFALL, district: KACHCHH }]);
});

test("a page from another state draws a stray figure even when a stray location names the district, one from the district does not", () => {
  const borrow = (slug: string, subject: SubjectPage["subject"] = "craft") => ({ path: subject === "category" ? `/categories/${slug}` : `/crafts/${slug}`, slug, subject, label: RAINFALL, district: KACHCHH });
  const stray = strayBorrows([borrow("Nizamabad-Black-Pottery"), borrow("Kutch-Bandhani"), borrow("Textiles", "category"), borrow("Bagh-Prints")], FACTS);
  expect(stray.map((found) => found.slug)).toEqual(["Nizamabad-Black-Pottery", "Bagh-Prints"]);
});

test("a category holds the crafts on its shelves and a family the crafts beside it", () => {
  const catalogue = {
    categories: [{ id: "c1", slug: "Textiles" }],
    crafts: [
      { slug: "Bagh-Prints", categoryId: "c1", subCategoryId: "s1" },
      { slug: "Hand-Block-Printing", categoryId: "c1", subCategoryId: "s1", isCatchAll: true },
      { slug: "Kutch-Bandhani", categoryId: "c1", subCategoryId: "s2" },
      { slug: "Bidriware", categoryId: "c2", subCategoryId: "s3" }
    ]
  };
  expect(pageMembers({ slug: "Textiles", subject: "category" }, catalogue)).toEqual(["Bagh-Prints", "Hand-Block-Printing", "Kutch-Bandhani"]);
  expect(pageMembers({ slug: "Hand-Block-Printing", subject: "family" }, catalogue)).toEqual(["Bagh-Prints", "Hand-Block-Printing"]);
  expect(pageMembers({ slug: "Bagh-Prints", subject: "craft" }, catalogue)).toEqual(["Bagh-Prints"]);
});

test("the map's district points say which crafts are located in each district", () => {
  const located = locatedCrafts([{ key: "district-449", crafts: [{ slug: "Kutch-Ajrakh" }, { slug: "Kutch-Bandhani" }] }, { key: "state-24", crafts: [{ slug: "Other" }] }]);
  expect([...located]).toEqual([[KACHCHH, ["Kutch-Ajrakh", "Kutch-Bandhani"]]]);
});
