import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { apiOrigin, borrowedCases, craftsWithClaims, pageKind, pagesToVisit, sameText, subjectPage, type SubjectPage } from "./parityBorrowed";
import { gatedDifferences } from "./parityComponent";
import { sharedOnce } from "./parityShared";

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
  const record = (fontSize: string, width: string, x = "0", display = "block") => ({ display, "font-size": fontSize, "box-width": width, "box-x": x });
  const approved = { "0:figure.rp": record("19px", "900"), "1:p.t": record("13px", "300"), "2:svg": record("19px", "20"), "3:a.inline": record("13px", "40", "520", "inline") };
  expect(gatedDifferences(approved, { "0:figure.rp": record("19px", "901"), "1:p.t": record("13px", "320"), "2:svg": record("19px", "21"), "3:a.inline": record("13px", "40", "528", "inline") })).toEqual([]);
  const placed = { ...record("19px", "900"), "margin-block-start": "56px", "box-height": "2149" };
  expect(gatedDifferences({ ...approved, "0:figure.rp": { ...record("19px", "900"), "margin-block-start": "80px", "box-height": "2125" } }, { ...approved, "0:figure.rp": placed })).toEqual([]);
  expect(gatedDifferences(approved, { "0:figure.rp": record("19px", "900"), "1:p.t": record("40px", "300"), "2:svg": record("19px", "900"), "3:a.inline": record("13px", "40", "520", "inline") }).map((found) => `${found.node} ${found.property}`)).toEqual([
    "1:p.t font-size",
    "2:svg box-width"
  ]);
});

test("only crafts that hold claims are read for a document, from the API a preview reads", () => {
  expect(craftsWithClaims([{ slug: "Bagru", depth: { claims: 324 } }, { slug: "Tharu", depth: { claims: 0 } }, { slug: "Sundari", depth: null }, { depth: { claims: 3 } }])).toEqual(["Bagru"]);
  expect(apiOrigin("https://kalavigyan-abc123def-cxacraftecosystem-8028s-projects.vercel.app")).toBe("https://kalavigyan.vercel.app");
  expect(apiOrigin("")).toBe("https://kalavigyan.vercel.app");
});

test("the documents are read once a run, however many workers ask", async () => {
  const folder = mkdtempSync(join(tmpdir(), "kv-parity-"));
  let made = 0;
  const make = async () => {
    made += 1;
    await new Promise((resolve) => setTimeout(resolve, 50));
    return { pages: made };
  };
  const found = await Promise.all([sharedOnce(folder, "pages", make), sharedOnce(folder, "pages", make), sharedOnce(folder, "pages", make)]);
  expect(made).toBe(1);
  expect(found).toEqual([{ pages: 1 }, { pages: 1 }, { pages: 1 }]);
});
