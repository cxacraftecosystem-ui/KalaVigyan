import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { motionAllowedNow, useMotionAllowed } from "@/components/motion/useMotionAllowed";
import { MOTION_CLASS, motionReduced, motionSwitches, parseDuration, VAT_STILL_STEP, vatSchedule, vatTimings } from "@/lib/motion";

import { scannedFiles } from "./designGuard";
import { FRONTEND } from "./moduleGraph";
import { primitivesPage } from "./primitivesPage";

const SCRIPT = /\.tsx?$/;
const SMOOTH = /"smooth"/g;
const GATED_SMOOTH = /\?\s*"smooth"\s*:\s*"auto"|\?\s*"auto"\s*:\s*"smooth"/g;
const TOKENS = readFileSync(join(FRONTEND, "app", "tokens.css"), "utf8");
const ROOT = TOKENS.slice(TOKENS.indexOf(":root {"), TOKENS.indexOf("}", TOKENS.indexOf(":root {")));
const token = (name: string) => new RegExp(`${name}:\\s*([^;]+);`).exec(ROOT)?.[1] ?? "";

const DEMO = [
  '<div class="motion-dip" id="dip" style="width:120px;height:80px;background:var(--dye-harda)"></div>',
  '<div class="motion-oxidise" id="oxidise" style="width:120px;height:80px;background:var(--dye-leuco)"></div>',
  '<button class="motion-press kv-switch" id="press" role="switch" aria-checked="true"></button>',
  '<div id="vat" data-vat-phase="in"><div class="vat-tint" id="tint" style="width:120px;height:80px;background:var(--dye-leuco)"></div></div>'
].join("");

async function playEverything(page: Page) {
  await page.evaluate(() => document.querySelectorAll(".motion-dip, .motion-oxidise, .motion-press").forEach((node) => node.setAttribute("data-playing", "")));
  return page.evaluate(() => {
    const style = (id: string) => getComputedStyle(document.getElementById(id)!);
    return {
      dip: style("dip").animationName,
      oxidise: style("oxidise").animationName,
      press: style("press").animationName,
      switch: style("press").transitionDuration,
      vat: style("tint").transitionDuration
    };
  });
}

test("motion is reduced when either switch is on: the system setting or the reader's own", () => {
  expect(motionReduced({ system: false, setting: false })).toBe(false);
  expect(motionReduced({ system: true, setting: false })).toBe(true);
  expect(motionReduced({ system: false, setting: true })).toBe(true);
  expect(motionSwitches({ dataset: { reducedMotion: "true" } }, { matches: false })).toEqual({ system: false, setting: true });
  expect(motionSwitches({ dataset: {} }, { matches: true })).toEqual({ system: true, setting: false });
  expect(motionSwitches(null, null)).toEqual({ system: false, setting: false });
});

test("the server and the first client render move nothing, so markup never depends on motion", () => {
  function Probe() {
    return createElement("span", null, String(useMotionAllowed()));
  }
  expect(renderToStaticMarkup(createElement(Probe))).toBe("<span>false</span>");
  expect(motionAllowedNow()).toBe(false);
});

test("the vat runs on the motion tokens: 800ms after the photograph, dip 600, hold 500, oxidise 1500, 2600ms in all", () => {
  expect(parseDuration("600ms")).toBe(600);
  expect(parseDuration("1.5s")).toBe(1500);
  expect(parseDuration(".8s")).toBe(800);
  expect(parseDuration("0.25s")).toBe(250);
  expect(() => parseDuration(".s")).toThrow("Not a CSS duration");
  expect(() => parseDuration("fast")).toThrow("Not a CSS duration");
  const timings = vatTimings(token);
  expect(timings).toEqual({ delay: 800, dip: 600, hold: 500, oxidise: 1500 });
  expect(vatSchedule(timings, true)).toEqual([
    { phase: "in", at: 800 },
    { phase: "lifted", at: 1400 },
    { phase: "air", at: 1900 },
    { phase: "rest", at: 3400 }
  ]);
  const replay = vatSchedule(timings, false);
  expect(replay.at(-1)?.at).toBe(parseDuration(token("--dur-vat")));
  expect(Object.values(MOTION_CLASS)).toEqual(["motion-press", "motion-dip", "motion-oxidise"]);
});

test("under reduced motion, Play again steps the vat one still phase at a time and comes back to rest", () => {
  const seen: string[] = [];
  let phase = "rest" as keyof typeof VAT_STILL_STEP;
  for (let press = 0; press < 5; press += 1) {
    phase = VAT_STILL_STEP[phase];
    seen.push(phase);
  }
  expect(seen).toEqual(["in", "lifted", "air", "rest", "in"]);
});

test("the vat tint is masked by the authored dyed region as well as the moving edges", async ({ page }) => {
  const mask = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E";
  await page.setContent(primitivesPage(`<div data-vat-phase="lifted"><div class="vat-tint" id="tint" style="--vat-mask:url(&quot;${mask}&quot;);width:120px;height:80px"></div><div class="vat-tint" id="plain" style="width:120px;height:80px"></div></div>`));
  const layers = await page.evaluate(() => ["tint", "plain"].map((id) => getComputedStyle(document.getElementById(id)!).maskImage));
  expect(layers[0].match(/linear-gradient\(/g)).toHaveLength(2);
  expect(layers[0]).toContain('url("data:image/svg+xml');
  expect(layers[1].match(/linear-gradient\(/g)).toHaveLength(3);
});

test("each named motion rests in its end state and plays only while neither switch is on", async ({ page }) => {
  await page.setContent(primitivesPage(DEMO));
  const resting = await page.evaluate(() => ({ dip: getComputedStyle(document.getElementById("dip")!).clipPath, oxidise: getComputedStyle(document.getElementById("oxidise")!).clipPath }));
  expect(resting).toEqual({ dip: "inset(0px)", oxidise: "inset(100% 0px 0px)" });
  expect(await playEverything(page)).toEqual({ dip: "kv-dip", oxidise: "kv-oxidise", press: "kv-press", switch: "0.2s, 0.2s", vat: "0.6s" });

  await page.setContent(primitivesPage(DEMO, 'data-reduced-motion="true"'));
  expect(await playEverything(page)).toEqual({ dip: "none", oxidise: "none", press: "none", switch: "0s", vat: "0s" });

  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setContent(primitivesPage(DEMO));
  expect(await playEverything(page)).toEqual({ dip: "none", oxidise: "none", press: "none", switch: "0s", vat: "0s" });
});

test("every scripted smooth scroll has an instant side, which either reduced-motion switch chooses", () => {
  const scripts = scannedFiles(FRONTEND).filter(({ key }) => SCRIPT.test(key));
  const ungated = scripts.filter(({ text }) => (text.match(SMOOTH)?.length ?? 0) > (text.match(GATED_SMOOTH)?.length ?? 0)).map(({ key }) => key);
  expect(ungated).toEqual([]);
  const roster = scripts.find(({ key }) => key === "app/(protected)/admin/access/page.tsx")?.text ?? "";
  expect(roster).toContain('scrollIntoView({ block: "start", behavior: motionAllowedNow() ? "smooth" : "auto" })');
});
