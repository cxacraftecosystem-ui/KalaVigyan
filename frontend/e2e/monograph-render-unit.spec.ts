import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { UnitView } from "../components/monograph/UnitView";
import type { MonographNode, MonographUnit } from "../lib/monographDocument";
import { citedNumbers, MonographMarkError, renderNodes, type MonographSources } from "../lib/monographRender";

import { PARITY } from "./monographParityCases";

const sources = PARITY.sources as unknown as MonographSources;
const cases = Object.entries(PARITY.units) as [string, { tag: string; nodes: unknown; html: string }][];
const nodesOf = (value: unknown) => value as MonographNode[];

test("every hand-picked unit renders exactly as the backend's render_nodes wrote it", () => {
  expect(cases.length).toBeGreaterThanOrEqual(15);
  for (const [ref, found] of cases) expect(renderNodes(nodesOf(found.nodes), sources), ref).toBe(found.html);
});

test("a unit's text writes an apostrophe and a straight quote as the approved page writes them", () => {
  expect(renderNodes(["Finer than Barmer's \"block\" prints & <dyes>"], sources)).toBe("Finer than Barmer&#x27;s &quot;block&quot; prints &amp; &lt;dyes&gt;");
});

test("the unit view draws the same markup in the unit's own element, straight quotes and apostrophes written as entities as render_nodes writes them", () => {
  for (const [ref, found] of cases) {
    const unit: MonographUnit = { chapter: "c", tag: found.tag, field: null, nodes: nodesOf(found.nodes), claimIds: [] };
    expect(renderToStaticMarkup(createElement(UnitView, { unit, sources })), ref).toBe(`<${found.tag}>${found.html}</${found.tag}>`);
  }
});

test("the unit view can draw a unit in the element and class its shell asks for", () => {
  const unit: MonographUnit = { chapter: "c", tag: "p", field: null, nodes: ["Fig. ", { m: "b", c: ["17"] }], claimIds: [] };
  expect(renderToStaticMarkup(createElement(UnitView, { unit, sources, as: "h2", className: "t-h2", id: "made-h" }))).toBe('<h2 class="t-h2" id="made-h">Fig. <b>17</b></h2>');
  expect(() => renderToStaticMarkup(createElement(UnitView, { unit, sources, as: "script" }))).toThrow(/not drawn as <script>/);
});

test("a citation cluster numbers its sources in order, once each, and names them", () => {
  expect(citedNumbers(["g2", "g1", "g2"], sources)).toEqual({ numbers: ["1", "2"], label: "Sources 1, 2", described: "GI Journal No. 188: Kutch Ajrakh; Ajrakh: Rhythm of Blues" });
  expect(citedNumbers(["g1"], sources).label).toBe("Source 1");
});

test("an unknown mark, an unknown source, a role outside the set and a script link are refused", () => {
  expect(() => renderNodes([{ m: "script", c: [] }], sources)).toThrow(MonographMarkError);
  expect(() => renderNodes([{ m: "cite", key: "k", g: ["g999"], c: ["x"] }], sources)).toThrow(/unknown sources g999/);
  expect(() => renderNodes([{ m: "i", role: "loud", c: ["x"] }], sources)).toThrow(/No italic role/);
  expect(() => renderNodes([{ m: "link", href: "javascript:alert(1)", c: ["x"] }], sources)).toThrow(/may not go to/);
  expect(() => renderNodes([{ m: "span", cls: 'a" onclick="x', c: ["x"] }], sources)).toThrow(/No class/);
});
