import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import {
  aliasClasses,
  arbitraryVars,
  baselineText,
  colourLiterals,
  GUARD_KINDS,
  guardCounts,
  hexColours,
  offListMedia,
  overBaseline,
  physicalUtilities,
  retiredClasses,
  scanFrontend,
  shrunkBaseline,
  type GuardBaseline
} from "./designGuard";
import { FRONTEND } from "./moduleGraph";

const BASELINE_FILE = join(FRONTEND, "e2e", "design-guard-baseline.json");
const baseline = JSON.parse(readFileSync(BASELINE_FILE, "utf8")) as GuardBaseline;

test("the guard finds retired ramp classes in every form a class string takes", () => {
  const text = 'className="bg-purple-700 dark:hover:bg-purple-950/40 text-gold-300! [&>b]:fill-errand-200 sm:border-s-steward-600 field-button text-field text-evidence-800" data-testid="field-voices"';
  expect(retiredClasses(text)).toEqual(["bg-purple-700", "bg-purple-950/40", "text-gold-300", "fill-errand-200", "border-s-steward-600", "text-evidence-800"]);
  expect(retiredClasses("@apply bg-ministry-50 ring-archive-300/20 to-mango-400;")).toEqual(["bg-ministry-50", "ring-archive-300/20", "to-mango-400"]);
  expect(retiredClasses("text-indigo bg-indigo-wash text-indigo-on hover:text-indigo-hover bg-turmeric-wash border-rule-strong fill-[var(--map-land)]")).toEqual([]);
});

test("the guard finds stock palette classes, which compile to nothing or to a stand-in, and black", () => {
  expect(retiredClasses("text-indigo-600 bg-blue-50 text-amber-700 bg-red-50 text-emerald-600 bg-black/40 fill-dye-red")).toEqual([
    "text-indigo-600",
    "bg-blue-50",
    "text-amber-700",
    "bg-red-50",
    "text-emerald-600",
    "bg-black/40",
    "fill-dye-red"
  ]);
});

test("the guard finds every migration alias and spares the named tokens", () => {
  const aliases = "text-ink-900 border-line-200 bg-surface-50 bg-bg-0 bg-card text-white text-sm text-2xl font-display font-bold font-mono rounded rounded-md rounded-t-lg shadow-sm shadow-island ease-spring text-error-600 bg-success-100";
  expect(aliasClasses(aliases)).toEqual(aliases.split(" "));
  expect(aliasClasses("text-ink-1 text-ink-3 border-rule bg-sunk bg-raised text-indigo-on text-ui text-h2 font-headline font-semibold font-code rounded-card rounded-full rounded-pill shadow-pop ease-out text-error bg-success-wash")).toEqual([]);
});

test("the guard finds physical left and right utilities and properties, and spares the logical ones", () => {
  expect(physicalUtilities("ml-auto pl-10 -right-2.5 left-1/2 text-left border-l rounded-r-md rounded-tl-sm float-right")).toEqual(["ml-auto", "pl-10", "-right-2.5", "left-1/2", "text-left", "border-l", "rounded-r-md", "rounded-tl-sm", "float-right"]);
  expect(physicalUtilities("ms-auto ps-10 -end-2.5 start-1/2 text-start border-s rounded-e-md inset-x-0 rect.left placement?.right")).toEqual([]);
  expect(physicalUtilities(".a { padding-right: 1rem; left: 0; text-align: right; padding-inline-end: 1rem; inset-inline-start: 0; }", true)).toEqual(["padding-right:", "left:", "text-align: right"]);
});

test("the guard spares locale tags, whose region is upper case, and still finds the utility beside them", () => {
  expect(physicalUtilities('{ mr: "mr-IN", ml: "ml-IN", lang: "pl-PL" }')).toEqual([]);
  expect(physicalUtilities('className="ml-4 mr-[2px]" lang="mr-IN"')).toEqual(["ml-4", "mr-[2px]"]);
});

test("the guard rejects media queries off the breakpoint list, in CSS, in variants and in matchMedia", () => {
  expect(offListMedia("@media (min-width: 700px) {} @media (min-width: 40rem) {} @media (width < 1024px) {} @media (max-width: 639.98px) {} @media (max-height: 560px) {}", true)).toEqual(["min-width: 700px", "min-width: 40rem"]);
  expect(offListMedia('className="min-[700px]:grid max-[639px]:hidden md:flex" matchMedia("(min-width: 1100px)") matchMedia("(min-width: 1200px)")')).toEqual(["min-[700px]:", "min-width: 1100px"]);
});

test("the guard finds var() arbitrary values outside the chart, map, cloth and craft folders, and colour literals", () => {
  expect(arbitraryVars("bg-[var(--map-land)] w-[calc(100%-var(--rail))] fill-(--fam-wood) bg-indigo")).toEqual(["[var(--", "[calc(100%-var(--", "-(--f"]);
  expect(guardCounts("components/map/Legend.tsx", "fill-[var(--map-land)]")).toEqual({});
  expect(guardCounts("components/answer/Thing.tsx", "fill-[var(--map-land)]")).toEqual({ arbitraryVar: 1 });
  expect(colourLiterals("box-shadow: 0 0 0 1px rgb(0 0 0 / 0.1); [accent-color:oklch(0.47_0.198_305)] rgb(var(--c-indigo)) hsl(210 40% 50%)")).toEqual(["rgb(0", "oklch(0", "hsl(2"]);
  expect(guardCounts("app/tokens.css", "--c: rgb(1 2 3); --d: #FFFFFF;")).toEqual({});
});

test("the guard finds hard-coded hex colours and spares entities, anchors and the sign-in brand marks", () => {
  expect(hexColours('fill="#FAF9F5" style={{ color: "#fff" }} stroke="#abcdef12"')).toEqual(["#FAF9F5", "#fff", "#abcdef12"]);
  expect(hexColours('&#160; href="#main" href="#chem" fill="#f25022" fill="#5f01d1" #12345')).toEqual([]);
});

for (const kind of GUARD_KINDS) {
  test(`no file has more ${kind} uses than its baseline`, () => {
    expect(overBaseline(scanFrontend(FRONTEND), baseline, kind)).toEqual([]);
  });
}

test("a file over its baseline, or new to it, is reported with both counts", () => {
  const recorded = { "a.tsx": { retired: 2, hex: 1 } };
  const now = { "a.tsx": { retired: 3, hex: 1, alias: 1 }, "b.tsx": { hex: 1 } };
  expect(overBaseline(now, recorded, "retired")).toEqual(["a.tsx: 3 retired, baseline 2"]);
  expect(overBaseline(now, recorded, "hex")).toEqual(["b.tsx: 1 hex, baseline 0"]);
  expect(overBaseline(now, recorded, "alias")).toEqual(["a.tsx: 1 alias, baseline 0"]);
});

test("shrinking keeps the lower count per file and kind, drops cleared files and never adds one", () => {
  const recorded = { "a.tsx": { retired: 3, hex: 2, physical: 4 }, "b.tsx": { retired: 1 } };
  const now = { "a.tsx": { retired: 5, hex: 1, alias: 7 }, "c.tsx": { retired: 4 } };
  expect(shrunkBaseline(now, recorded)).toEqual({ "a.tsx": { retired: 3, hex: 1 } });
  expect(baselineText({ "a.tsx": { retired: 3, hex: 1 } })).toBe('{\n  "a.tsx": { "retired": 3, "hex": 1 }\n}\n');
});

test("the recorded baseline is in shrunk form", () => {
  expect(readFileSync(BASELINE_FILE, "utf8")).toBe(baselineText(shrunkBaseline(baseline, baseline)));
});

test("recording lower counts rewrites the baseline", () => {
  test.skip(process.env.DESIGN_GUARD_SHRINK !== "1", "set DESIGN_GUARD_SHRINK=1 to record lower counts");
  writeFileSync(BASELINE_FILE, baselineText(shrunkBaseline(scanFrontend(FRONTEND), baseline)));
});
