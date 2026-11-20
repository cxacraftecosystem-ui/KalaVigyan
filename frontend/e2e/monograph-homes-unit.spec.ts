import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ComponentHome } from "../components/monograph/ComponentHome";
import type { MonographComponent, MonographDocument, MonographUnit } from "../lib/monographDocument";
import { numberedDocument } from "../lib/monographRenderFigures";
import { pagePlan, type PagePlan } from "../lib/monographRenderLayout";
import { placedPlan } from "../lib/monographRenderNear";
import { componentHome } from "../lib/monographScopes";

const CHAIN = "shared/chemistry/indigo-leaf-to-cloth-chain";
const VAT = "test-craft/chemistry/vat";
const MADDER = "test-craft/chemistry/alizarin";
const PLAYER = "test-craft/chemistry/player";
const STEPS = "test-craft/chemistry/steps";

const sentence = (text: string): MonographUnit["nodes"] => [{ m: "s", c: [text] }];
const unit = (tag: string, nodes: MonographUnit["nodes"], field: string | null = null): MonographUnit => ({ chapter: "chem", tag, field, nodes, claimIds: [] });
const component = (label: string, kind: string, title: string, description: string): MonographComponent => ({
  label,
  chapter: "chem",
  anchor: `#${label}`,
  kind,
  title,
  description,
  field: "CHEMISTRY",
  fields: [],
  subjects: []
});

function document(units: Record<string, MonographUnit>, components: MonographComponent[], specs: MonographDocument["specs"]): MonographDocument {
  const refs = Object.keys(units).filter((ref) => ref !== "u0000");
  return {
    schemaVersion: 1,
    subjectKind: "category",
    subjectSlug: "Test-Category",
    language: "en",
    title: "Test category",
    version: 1,
    pageUrl: "https://kalavigyan.example/categories/Test-Category",
    shell: null,
    content: {
      schemaVersion: 1,
      craftSlug: "Test-Category",
      sources: {},
      citations: {},
      citationClaims: {},
      data: {},
      units: { u0000: { ...unit("p", ["Test category"]), chapter: "opening" }, ...units },
      components,
      layout: [
        { chapter: "opening", kind: "unit", ref: "u0000", within: null },
        ...refs.map((ref) => ({ chapter: "chem", kind: "unit" as const, ref, within: null })),
        ...components.map((found) => ({ chapter: "chem", kind: "component" as const, ref: found.label, within: null }))
      ]
    },
    specs,
    fragments: {}
  };
}

test("a borrowed component is drawn in the scope and frame of its slot on the authored page", () => {
  const home = componentHome(CHAIN, "diagram", null);
  expect(home.source).toBe("home");
  expect(home.scope).toBe("ask");
  expect(home.frame).toEqual([
    { classes: ["screen"], box: true },
    { classes: ["kv-chain"], box: false },
    { classes: ["kv-wrap"], box: true }
  ]);
  const html = renderToStaticMarkup(createElement(ComponentHome, { home, label: CHAIN, kind: "diagram" }, createElement("section", { className: "chain" })));
  expect(html).toBe(`<div class="bx bx-ask my-12" data-component="${CHAIN}" data-component-kind="diagram" data-home="home"><div class="screen"><div class="kv-chain" style="display:contents"><div class="kv-wrap"><section class="chain"></section></div></div></div></div>`);
});

test("a contributed component takes the scope its kind's authored specs of the same shape are drawn in", () => {
  expect(componentHome("test-craft/chemistry/chain", "diagram", { chain: { heading: "u0001" }, drawing: null })).toMatchObject({ scope: "ask", source: "kind" });
  expect(componentHome("test-craft/geography/distances", "diagram", { chain: null, drawing: { tag: "svg" } })).toMatchObject({ scope: "mb", source: "kind" });
  expect(componentHome("test-craft/pictures/p1", "picture_plate", { figure: {}, picture: {}, setting: "column" })).toMatchObject({ scope: "pt", source: "kind" });
  expect(componentHome("test-craft/blocks/b1", "answer_block", { block: {} })).toMatchObject({ scope: "mb", source: "app" });
});

function chemistry(): MonographDocument {
  return document(
    {
      u0001: unit("h2", ["The chemistry"]),
      u0002: unit("p", sentence("Dyes hold to cloth in many ways.")),
      u0003: unit("p", sentence("Each dye has its own chemistry.")),
      u0004: unit("p", sentence("Some need a mordant.")),
      u0005: unit("p", sentence("Indigo is reduced in the vat to leucoindigo."), "CHEMISTRY"),
      u0006: unit("p", sentence("The reduced liquor turns yellow green."), "CHEMISTRY"),
      u0007: unit("p", sentence("Madder roots give alizarin."), "MATERIALS"),
      u0008: unit("p", sentence("Alizarin binds alum on cotton."), "MATERIALS")
    },
    [component(VAT, "dip_player", "The indigo vat", "Indigo reduced to leucoindigo."), component(MADDER, "molecule_3d", "Alizarin and purpurin", "The madder dyes alizarin and purpurin.")],
    {}
  );
}

test("a figure left at the end of a chapter stands after the paragraph it illustrates", () => {
  const given = chemistry();
  const plan = placedPlan(given, pagePlan(given));
  const chem = plan.chapters.find((chapter) => chapter.key === "chem")!;
  expect(chem.blocks.map((block) => (block.kind === "component" ? block.label : block.kind === "passage" ? block.pieces.map((piece) => (piece.kind === "paragraph" ? piece.refs.join("+") : piece.kind)).join(",") : block.kind))).toEqual([
    "unit,u0002+u0003+u0004,u0005+u0006",
    VAT,
    "u0007+u0008",
    MADDER
  ]);
  expect(chem.blocks.filter((block) => block.kind === "passage").map((block) => block.kind === "passage" && block.head)).toEqual([true, false]);
});

test("a figure an editor placed keeps its place, and the authored page is never rearranged", () => {
  const given = chemistry();
  given.content.data = { "page-layout": { entries: [{ ref: MADDER, chapter: "chem", order: 9, role: "FIGURE" }] } };
  const chem = placedPlan(given, pagePlan(given)).chapters.find((chapter) => chapter.key === "chem")!;
  expect(chem.blocks.map((block) => (block.kind === "component" ? block.label : block.kind))).toEqual(["passage", VAT, "passage", MADDER]);
  const authored = { ...chemistry(), shell: "<main></main>" };
  const plan = pagePlan(authored);
  expect(placedPlan(authored, plan)).toBe(plan);
});

test("figures borrowed from another page are numbered again in this page's order, with their references", () => {
  const given = document(
    { u0010: unit("p", ["Fig. 6"]), u0011: unit("p", ["Fig. ", { m: "b", c: ["3"] }]), u0012: unit("p", ["See ", { m: "figref", ref: "chem:2", c: ["Fig. 3"] }, "."]) },
    [component(MADDER, "molecule_3d", "Alizarin", "Madder."), component(PLAYER, "reaction_player", "Indigo", "The vat."), component(STEPS, "diagram", "Chain", "Leaf to cloth.")],
    {
      [MADDER]: { head: { figure: "chem:5", number: "u0010", title: "u0010" } },
      [PLAYER]: { id: "rp-blue", head: { figure: "chem:2", number: "u0011", title: "u0011" } },
      [STEPS]: { chain: { links: [{ parts: [{ part: "step", player: "rp-blue", step: 1, figure: "chem:3", figureLabel: "Fig. 4" }] }] } }
    }
  );
  const blocks = [MADDER, PLAYER, STEPS].map((label) => ({ kind: "component" as const, label }));
  const plan: PagePlan = { masthead: { kicker: null, standfirst: [], lede: null, picture: null }, label: null, chapters: [{ key: "chem", index: 1, number: 1, label: "The chemistry", blocks }] };
  const shown = numberedDocument(given, plan);
  expect([shown.content.units.u0010.nodes, shown.content.units.u0011.nodes]).toEqual([["Fig. 1"], ["Fig. ", { m: "b", c: ["2"] }]]);
  expect(shown.content.units.u0012.nodes).toEqual(["See ", { m: "figref", ref: "chem:2", c: ["Fig. 2"] }, "."]);
  expect(JSON.stringify(shown.specs[STEPS])).toContain('"figureLabel":"Fig. 2"');
  expect(given.content.units.u0010.nodes).toEqual(["Fig. 6"]);
});
