import { expect, test } from "@playwright/test";

import type { DrawnElement } from "./figureBrowser";
import { figureDifferences, heldDifferences, offsetDifferences, tally, withoutIdReferences } from "./figureCheck";
import { complexSelectors, declaredNames, isRootCompound, layerOrder, matchingForm, nestedCss, rootScopedSelector, scopedSelector, structuralSelectors, varNames, type SheetRead } from "./figureCss";
import { emptyFrame, figureFragment, withStyle } from "./figureMarkup";
import { figureStyles, inheritedResidue, residueRule } from "./figureRules";

const SCOPE = ".s";

test("a selector list splits at its own commas, not those inside brackets, strings or escapes", () => {
  expect(complexSelectors(".a, .b > .c")).toEqual([".a", ".b > .c"]);
  expect(complexSelectors(':is(.a, .b) .c, [data-x="1,2"]')).toEqual([":is(.a, .b) .c", '[data-x="1,2"]']);
  expect(complexSelectors(".lg\\:grid-cols-\\[minmax\\(0\\,7fr\\)\\], .x")).toEqual([".lg\\:grid-cols-\\[minmax\\(0\\,7fr\\)\\]", ".x"]);
});

test("a selector is matched without its states, pseudo-elements and the root's theme condition", () => {
  expect(matchingForm(".kv-link:hover")).toBe(".kv-link");
  expect(matchingForm(".a :hover")).toBe(".a *");
  expect(matchingForm("::before")).toBe("*");
  expect(matchingForm(".a > ::after")).toBe(".a > *");
  expect(matchingForm(':root[data-theme="dark"] .kv-figure:focus-visible::before')).toBe(".kv-figure");
  expect(matchingForm("html .y")).toBe(".y");
  expect(matchingForm("a:not(:hover)")).toBe("a:not(:hover)");
  expect(matchingForm(".x:first-child")).toBe(".x:first-child");
});

test("only a single compound on the root element declares the page's tokens", () => {
  expect(isRootCompound(":root")).toBe(true);
  expect(isRootCompound(':root:not([data-theme="light"])')).toBe(true);
  expect(isRootCompound("html")).toBe(true);
  expect(isRootCompound(":root .x")).toBe(false);
  expect(isRootCompound("html[data-a] > body")).toBe(false);
  expect(isRootCompound(".x")).toBe(false);
});

test("a kept selector keeps its specificity and reaches only the figure and what it holds", () => {
  expect(scopedSelector(".a", SCOPE)).toBe(":is(.a):where(.s, .s *)");
  expect(scopedSelector(".a::before", SCOPE)).toBe(":is(.a):where(.s, .s *)::before");
  expect(scopedSelector("::after", SCOPE)).toBe(":is(*):where(.s, .s *)::after");
  expect(scopedSelector(".a:hover", SCOPE)).toBe(":is(.a:hover):where(.s, .s *)");
  expect(rootScopedSelector(':root[data-theme="dark"]', SCOPE)).toBe(':is(:root[data-theme="dark"]) :where(.s)');
});

test("the tokens a rule reads and declares are named once each", () => {
  expect(varNames("color: var(--ink-1); fill: var( --map-water, var(--x)); stroke: var(--ink-1)")).toEqual(["--ink-1", "--map-water", "--x"]);
  expect(declaredNames(":is(.a) { --tw-font-weight: 500; font-weight: var(--tw-font-weight); }")).toEqual(["--tw-font-weight"]);
});

test("rules open and close their layers and conditions in the order they came", () => {
  const rules = [
    { chain: ["@layer base"], text: "a {}" },
    { chain: ["@layer base"], text: "b {}" },
    { chain: ["@layer base", "@media (x)"], text: "c {}" },
    { chain: [], text: "d {}" }
  ];
  expect(nestedCss(rules)).toBe("@layer base {\na {}\nb {}\n@media (x) {\nc {}\n}\n}\nd {}");
  expect(layerOrder([{ chain: ["@layer components"], text: "" }, { chain: ["@layer base", "@media (x)"], text: "" }], ["properties", "theme", "base", "components", "utilities"])).toBe("@layer base, components;");
  expect(structuralSelectors([{ chain: [], text: ":is(.a:first-child):where(.s, .s *) { x }" }, { chain: [], text: ":is(.b):where(.s, .s *) { y }" }], SCOPE)).toEqual([":is(.a:first-child):where(.s, .s *)"]);
});

const SHEETS: SheetRead = {
  kit: 1,
  layers: ["theme", "utilities"],
  sheets: ["app.css", "kit.css"],
  entries: [
    { kind: "style", sheet: 0, chain: ["@layer theme"], selector: ":root, :host", body: "--spacing: .25rem;", vars: [["--spacing", ".25rem", ""]] },
    { kind: "style", sheet: 0, chain: [], selector: ":root", body: "--ink-1: #111; --unused: 1px; --map-water: #9cf;", vars: [["--ink-1", "#111", ""], ["--unused", "1px", ""], ["--map-water", "#9cf", ""]] },
    { kind: "style", sheet: 0, chain: ["@media (prefers-color-scheme: dark)"], selector: ':root:not([data-theme="light"])', body: "--ink-1: #eee;", vars: [["--ink-1", "#eee", ""]] },
    { kind: "style", sheet: 0, chain: ["@layer utilities"], selector: ".p-3", body: "padding: calc(var(--spacing) * 3);", vars: [] },
    { kind: "style", sheet: 0, chain: ["@layer utilities"], selector: ".text-ink-1", body: "color: var(--ink-1);", vars: [] },
    { kind: "style", sheet: 0, chain: ["@layer utilities"], selector: ".mt-9", body: "margin-top: 9px;", vars: [] },
    { kind: "property", sheet: 0, name: "--tw-font-weight", text: '@property --tw-font-weight { syntax: "*"; inherits: false; }' },
    { kind: "style", sheet: 1, chain: [], selector: ":root", body: "--map-water: #abc;", vars: [["--map-water", "#abc", ""]] },
    { kind: "style", sheet: 0, chain: ["@layer utilities"], selector: ".font-medium", body: "--tw-font-weight: 500; font-weight: 500;", vars: [["--tw-font-weight", "500", ""]] },
    { kind: "style", sheet: 0, chain: ["@layer utilities"], selector: ".kv-vat", body: "--vat: 0%;", vars: [["--vat", "0%", ""]] },
    { kind: "property", sheet: 0, name: "--vat", text: '@property --vat { syntax: "<percentage>"; inherits: false; }' },
    { kind: "property", sheet: 1, name: "--vat", text: '@property --vat { syntax: "<percentage>"; inherits: true; }' }
  ]
};

test("the figure keeps the app rules that match it, the tokens they read that the kit does not set later, and the registered properties the kit does not use", () => {
  const styles = figureStyles(SHEETS, new Set([".p-3", ".text-ink-1", ".font-medium", ".kv-vat"]), '<div class="kv-why-here" data-app=""><svg fill="var(--map-water)"></svg></div>', SCOPE);
  expect(styles.css).toBe(
    [
      "@layer theme, utilities;",
      '@property --tw-font-weight { syntax: "*"; inherits: false; }',
      "@layer theme {",
      ":is(:root) :where(.s) { --spacing: .25rem; }",
      "}",
      ":is(:root) :where(.s) { --ink-1: #111; }",
      "@media (prefers-color-scheme: dark) {",
      ':is(:root:not([data-theme="light"])) :where(.s) { --ink-1: #eee; }',
      "}",
      "@layer utilities {",
      ":is(.p-3):where(.s, .s *) { padding: calc(var(--spacing) * 3); }",
      ":is(.text-ink-1):where(.s, .s *) { color: var(--ink-1); }",
      ":is(.font-medium):where(.s, .s *) { --tw-font-weight: 500; font-weight: 500; }",
      ":is(.kv-vat):where(.s, .s *) { --vat: 0%; }",
      "}"
    ].join("\n")
  );
  expect(styles.vars).toEqual(["--ink-1", "--map-water", "--spacing"]);
  expect([styles.matched, styles.tokens, styles.properties]).toEqual([4, 3, 1]);
});

test("the fragment drops React's markers, names its ids once and for all, and carries its styles first", () => {
  const drawn = '<div class="kv-page kv-why-here" data-app=""><!-- --><svg aria-labelledby="«r5»-t «r5»-d"><title id="«r5»-t">T</title><desc id="«r5»-d">D</desc><rect fill="url(#«r5»-salt)"></rect><defs><pattern id="«r5»-salt"></pattern></defs></svg><div id="«r6»">x</div></div>';
  expect(figureFragment(drawn, "a { b: c; }", "kv-why-here")).toBe(
    '<div class="kv-page kv-why-here" data-app=""><style>a { b: c; }</style><svg aria-labelledby="kv-why-here-1 kv-why-here-2"><title id="kv-why-here-1">T</title><desc id="kv-why-here-2">D</desc><rect fill="url(#kv-why-here-3)"></rect><defs><pattern id="kv-why-here-3"></pattern></defs></svg><div id="kv-why-here-4">x</div></div>'
  );
  expect(() => withStyle("<div></div>", "a { content: '</style>'; }")).toThrow(/close their style element/);
});

function drawn(tag: string, svg: boolean, inner: boolean, box: string, props: Record<string, string>): DrawnElement {
  return { tag, svg, inner, box, props };
}

test("away from the capture width only the map's own drawing may differ, and the ids that move are named", () => {
  const approved = [drawn("div", false, false, "0 0 100 50", { color: "red" }), drawn("svg", true, false, "0 0 10 5", { "--k": "1.0" }), drawn("circle", true, true, "1 1 2 2", { r: "5px" })];
  const rendered = [drawn("div", false, false, "0 0 100 50", { color: "blue" }), drawn("svg", true, false, "0 0 10 6", { "--k": "1.1" }), drawn("circle", true, true, "1 1 3 3", { r: "6px" })];
  const differences = figureDifferences(approved, rendered);
  expect(differences.map((found) => `${found.tag} ${found.property}`)).toEqual(["div color", "svg --k", "svg box", "circle r", "circle box"]);
  expect(heldDifferences(differences, false).map((found) => `${found.tag} ${found.property}`)).toEqual(["div color", "svg box"]);
  expect(heldDifferences(differences, true)).toHaveLength(5);
  expect(tally(differences).box.count).toBe(2);
  expect(figureDifferences(approved, [])[0].property).toBe("figure");
  expect(offsetDifferences({ a: "1.00", b: "2.00", c: "3.00" }, { a: "1.00", b: "2.50" })).toEqual([{ id: "b", approved: "2.00", rendered: "2.50" }]);
});

test("the frame takes only what it inherits on the React page and the approved page does not give it", () => {
  const residue = inheritedResidue({ "tab-size": "4", color: "red", height: "10px" }, { "tab-size": "4", color: "red", height: "99px" }, { "tab-size": "8", color: "red", height: "0px" });
  expect(residue).toEqual({ "tab-size": "4" });
  expect(residueRule(residue, SCOPE)).toBe(":where(.s) { tab-size: 4; }");
  expect(residueRule({}, SCOPE)).toBe("");
  expect(emptyFrame('<div class="kv-page" data-app=""><figure></figure></div>', "a {}")).toBe('<div class="kv-page" data-app=""><style>a {}</style></div>');
});

test("a fill that points at a renamed pattern reads the same on both pages", () => {
  expect(withoutIdReferences('url("#kv-why-here-3")')).toBe("url(#)");
  expect(withoutIdReferences('url("#_r_0_-salt")')).toBe("url(#)");
  expect(withoutIdReferences("rgb(1, 2, 3)")).toBe("rgb(1, 2, 3)");
});
