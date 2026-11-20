import { expect, test } from "@playwright/test";

import { borrowedCases, pageKind, pagesToVisit, sameText, subjectPage, type SubjectPage } from "./parityBorrowed";
import { gatedDifferences } from "./parityComponent";

const CHAIN = "shared/chemistry/indigo-leaf-to-cloth-chain";
const PLAYER = "shared/chemistry/indigo-reduction-player";

function page(slug: string, subject: SubjectPage["subject"], labels: [string, string][], curated = false): SubjectPage {
  return { path: subject === "category" ? `/categories/${slug}` : `/crafts/${slug}`, slug, subject, curated, authored: false, components: labels.map(([label, kind]) => ({ label, kind })) };
}

test("a document read from the site is a page of its subject, curated when it carries structure blocks", () => {
  const body = { subjectKind: "craft", shell: null, content: { components: [{ label: "bagru/blocks/x", kind: "answer_block" }] } };
  expect(subjectPage(body, "craft", "Bagru")).toMatchObject({ path: "/crafts/Bagru", subject: "craft", curated: true, authored: false });
  expect(subjectPage({ ...body, subjectKind: "category" }, "category", "Textiles")?.path).toBe("/categories/Textiles");
  expect(pageKind(page("Cane", "family", []))).toBe("family");
  expect(subjectPage({ subjectKind: "poster" }, "craft", "X")).toBeNull();
});

test("each borrowed component is checked once per kind of page, and every kind of page is visited", () => {
  const pages = [
    page("Bagru", "craft", [[CHAIN, "diagram"], [PLAYER, "reaction_player"]], true),
    page("Textiles", "category", [[CHAIN, "diagram"]]),
    page("Sanganeri", "craft", [[CHAIN, "diagram"]], true),
    page("Cane", "family", [["cane/blocks/x", "answer_block"]]),
    page("Odd", "craft", [[CHAIN, "chart"]])
  ];
  const cases = borrowedCases(pages);
  expect(cases.map((found) => `${found.label} ${found.page.slug}`)).toEqual([`${CHAIN} Textiles`, `${CHAIN} Bagru`, `${PLAYER} Bagru`]);
  expect(cases[0].root).toBe("section.chain");
  expect(cases[0].frame).toBe(3);
  expect(pagesToVisit(cases, pages).map((found) => found.slug)).toEqual(["Textiles", "Bagru", "Cane", "Odd"]);
});

test("the authored copy of a component is the one whose words match, numbers aside", () => {
  expect(sameText("Fig. 6 Madder 14", "Fig. 2 Madder 3")).toBe(1);
  expect(sameText("Fig. 3 Indigo", "Fig. 3 Alizarin")).toBeLessThan(1);
});

test("a drawing differs where a style differs, or where a box, a graphic or the root moves more than two pixels", () => {
  const record = (fontSize: string, width: string) => ({ "font-size": fontSize, "box-width": width, "box-x": "0" });
  const approved = { "0:figure.rp": record("19px", "900"), "1:p.t": record("13px", "300"), "2:svg": record("19px", "20") };
  expect(gatedDifferences(approved, { "0:figure.rp": record("19px", "901"), "1:p.t": record("13px", "320"), "2:svg": record("19px", "21") })).toEqual([]);
  expect(gatedDifferences(approved, { "0:figure.rp": record("19px", "900"), "1:p.t": record("40px", "300"), "2:svg": record("19px", "900") }).map((found) => `${found.node} ${found.property}`)).toEqual([
    "1:p.t font-size",
    "2:svg box-width"
  ]);
});
