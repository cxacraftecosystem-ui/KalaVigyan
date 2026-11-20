import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AuthProvider } from "../components/AuthProvider";
import { ChapterRail } from "../components/editorial/ChapterRail";
import { MonographRail, RAIL_ARROWS, RAIL_LIST_ID } from "../components/monograph/MonographRail";
import { ThemeProvider } from "../components/ThemeProvider";
import { railArrowShown, railEnds, railMask, railStep, railTarget } from "../lib/monographRail";
import type { ChapterPlan } from "../lib/monographRenderLayout";

const chapter = (key: string, number: number | null, label: string): ChapterPlan => ({ key, index: number ?? 0, number, label, blocks: [] });
const provided = (element: ReactElement) => renderToStaticMarkup(createElement(AuthProvider, null, createElement(ThemeProvider, null, element)));
const CHAPTERS = [chapter("answer", null, "Answer"), chapter("cloth", 1, "The cloth"), chapter("sources", 2, "Sources")];

test("a rail that fits shows no fade and no arrows, and one that overflows fades each edge that hides chapters", () => {
  expect(railEnds(0, 900, 900)).toEqual({ over: false, back: 0, on: 0 });
  expect(railEnds(0, 1600, 1000)).toEqual({ over: true, back: 0, on: 48 });
  expect(railEnds(20, 1600, 1000)).toEqual({ over: true, back: 20, on: 48 });
  expect(railEnds(300, 1600, 1000)).toEqual({ over: true, back: 48, on: 48 });
  expect(railEnds(590, 1600, 1000)).toEqual({ over: true, back: 48, on: 10 });
  expect(railEnds(600, 1600, 1000)).toEqual({ over: true, back: 48, on: 0 });
  expect(railEnds(-300, 1600, 1000)).toEqual({ over: true, back: 48, on: 48 });
  expect(railArrowShown(railEnds(0, 1600, 1000), "back")).toBe(false);
  expect(railArrowShown(railEnds(0, 1600, 1000), "on")).toBe(true);
  expect(railArrowShown(railEnds(600, 1600, 1000), "on")).toBe(false);
  expect(railMask({ over: true, back: 20, on: 48 })).toBe("linear-gradient(90deg, transparent, black 20px, black calc(100% - 48px), transparent)");
  expect(railMask({ over: true, back: 0, on: 48 }, true)).toBe("linear-gradient(270deg, transparent, black 0px, black calc(100% - 48px), transparent)");
});

test("an arrow scrolls about one view, and the current chapter is brought into view only when it sits under a fade", () => {
  expect(railStep(1000)).toBe(904);
  expect(railStep(150)).toBe(120);
  const list = { left: 100, right: 1100, width: 1000 };
  expect(railTarget(list, { left: 400, right: 500, width: 100 }, 250)).toBeNull();
  expect(railTarget(list, { left: 1080, right: 1180, width: 100 }, 250)).toBe(250 + 980 - 450);
  expect(railTarget(list, { left: 110, right: 210, width: 100 }, 250)).toBe(250 + 10 - 450);
});

test("the monograph rail carries two labelled arrow buttons, hidden until the list overflows, that control the list", () => {
  const html = provided(createElement(MonographRail, { chapters: CHAPTERS }));
  expect(html).toContain(`<ol id="${RAIL_LIST_ID}">`);
  expect(html).toContain(`<button class="kv-rail-go" type="button" data-go="back" aria-label="${RAIL_ARROWS.back.label}" aria-controls="${RAIL_LIST_ID}" hidden="">`);
  expect(html).toContain(`<button class="kv-rail-go" type="button" data-go="on" aria-label="${RAIL_ARROWS.on.label}" aria-controls="${RAIL_LIST_ID}" hidden="">`);
  expect(html.indexOf('data-go="back"')).toBeLessThan(html.indexOf(`id="${RAIL_LIST_ID}"`));
  expect(html.indexOf('data-go="on"')).toBeGreaterThan(html.indexOf("</ol>"));
});

test("the approved page's rail carries the same arrows as the React rail", () => {
  const template = readFileSync(join(__dirname, "..", "..", "backend", "app", "data", "monographs", "Kutch-Ajrakh", "template.html"), "utf8");
  const react = provided(createElement(MonographRail, { chapters: CHAPTERS }));
  for (const go of ["back", "on"] as const) {
    const button = react.match(new RegExp(`<button class="kv-rail-go"[^>]*data-go="${go}"[\\s\\S]*?</button>`))?.[0] ?? "";
    const authored = template.match(new RegExp(`<button class="kv-rail-go"[^>]*data-go="${go}"[\\s\\S]*?</button>`))?.[0] ?? "";
    expect(authored).toContain(`data-go="${go}"`);
    expect(authored.replace(/hidden(="")?/, "hidden")).toBe(button.replace(/hidden(="")?/, "hidden").replace(/><\/path>/g, "/>"));
  }
  expect(template).toContain(`<div class="kv-rail-in"><button class="kv-rail-go"`);
  expect(template).toContain(`<ol id="${RAIL_LIST_ID}">`);
});

test("the editorial chapter rail renders its chapters at rest and adds arrows only once it measures an overflow", () => {
  const html = renderToStaticMarkup(createElement(ChapterRail, { chapters: [{ id: "glance", label: "At a glance" }, { id: "chem", label: "The chemistry" }] }));
  expect(html).toContain('<a href="#glance" aria-current="location"><b>1</b>At a glance</a>');
  expect(html).not.toContain("Show later chapters");
});

test("the kit fades the rail by the edges the script measures and sets each arrow in the margin", () => {
  const css = readFileSync(join(__dirname, "..", "..", "backend", "app", "data", "monographs", "kit", "monograph.css"), "utf8");
  const script = readFileSync(join(__dirname, "..", "..", "backend", "app", "data", "monographs", "kit", "monograph.js"), "utf8");
  expect(css).toContain(".kv-rail[data-edges] ol { -webkit-mask-image: linear-gradient(90deg, transparent, #000 var(--rail-back, 0px), #000 calc(100% - var(--rail-on, 0px)), transparent);");
  expect(css).toContain(".kv-rail-go[hidden] { display: none; }");
  expect(script).toContain("rail.setAttribute('data-edges', ends.over ? 'over' : 'fit');");
  expect(script).toContain("railList.scrollBy({ left: dir * step, behavior: reduced() ? 'auto' : 'smooth' });");
});
