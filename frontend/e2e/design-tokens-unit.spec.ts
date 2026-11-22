import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { SOUND_BAR_STAGGER_MS, SoundBars } from "@/components/ask/DictationControl";
import { CHOROPLETH_TONES } from "@/components/map/DistrictLayer";
import { PREFERENCES_BOOT_SCRIPT, THEME_COLOR } from "@/lib/preferences";
import { FRONTEND } from "./moduleGraph";

const read = (...parts: string[]) => readFileSync(join(FRONTEND, ...parts), "utf8");
const TOKENS = read("app", "tokens.css");
const GLOBALS = read("app", "globals.css");
const MOTION = read("app", "motion.css");

const SEMANTIC: Record<string, [string, string, string, string]> = {
  ground: ["#F4F5F1", "#0E121C", "#FFFFFF", "#000000"],
  raised: ["#FBFBF9", "#161B28", "#FFFFFF", "#0E121C"],
  sunk: ["#E8EAE4", "#0A0D15", "#EEF0EA", "#05070C"],
  rule: ["#D2D6CE", "#2A3142", "#8A9088", "#7F889C"],
  "rule-strong": ["#767C74", "#7A849A", "#3D433C", "#C4CBD8"],
  "ink-1": ["#1C1815", "#ECEAE3", "#000000", "#FFFFFF"],
  "ink-2": ["#3A3430", "#CBC8C0", "#1C1815", "#F1EFE9"],
  "ink-3": ["#59534E", "#A5A198", "#2E2925", "#D9D6CE"],
  indigo: ["#243B9C", "#A9BCF3", "#172881", "#C9D5FB"],
  "indigo-hover": ["#162779", "#CBD7FA", "#0C1761", "#E2E9FD"],
  "indigo-wash": ["#DFE6F6", "#1E2849", "#D3DCF4", "#24305A"],
  "on-indigo": ["#FBFBF9", "#0E121C", "#FFFFFF", "#000000"],
  madder: ["#9E2E27", "#EF8E80", "#7A1D18", "#FFAFA3"],
  "madder-wash": ["#F4DFDB", "#3B2124", "#F4DAD5", "#45242A"],
  "on-madder": ["#FBFBF9", "#0E121C", "#FFFFFF", "#000000"],
  turmeric: ["#E6AE2A", "#F0C152", "#E6AE2A", "#FFD166"],
  "turmeric-wash": ["#F8E6A8", "#4A3A12", "#F8E09A", "#5A4614"],
  "turmeric-text": ["#7A5300", "#F0C152", "#5A3D00", "#FFD166"],
  terracotta: ["#B05A36", "#E0916C", "#7D3519", "#F5AE8C"],
  error: ["#9E2E27", "#EF8E80", "#7A1D18", "#FFAFA3"],
  "error-wash": ["#F4DFDB", "#3B2124", "#F4DAD5", "#45242A"],
  warning: ["#8A4A12", "#F0A868", "#6A3608", "#FFC08A"],
  "warning-wash": ["#F6E4D2", "#3D2A17", "#F4DCC4", "#4A3016"],
  info: ["#2F5266", "#84A5B0", "#1F3D4F", "#A1BCCA"],
  "info-wash": ["#DDE7EC", "#16252F", "#D2E1E8", "#1A2C38"],
  success: ["#2E6A41", "#8CC79A", "#1F4F2E", "#AEE0BA"],
  "success-wash": ["#DCEADF", "#16281C", "#D0E6D5", "#173020"]
};

const steps = (prefix: string, count: number) => Array.from({ length: count }, (_, index) => `--${prefix}-${index + 1}`);
const PLATES = ["textile", "metal", "wood", "fibre", "clay", "stone", "paper", "leather", "paint", "instr", "toys", "misc"];
const THEMED = [
  ...Object.keys(SEMANTIC).map((name) => `--c-${name}`),
  ...PLATES.flatMap((plate) => [`--plate-${plate}`, `--plate-${plate}-ink`]),
  ...steps("rain", 6), ...steps("density", 6), ...steps("heat", 6), ...steps("ph", 5), ...steps("elevation", 7),
  ...["textiles", "metal", "wood", "paper", "clay", "stone", "leather", "fibre", "other"].map((family) => `--fam-${family}`),
  ...["axis-text", "axis-line", "grid", "series", "emph", "reference", "trend", "band", "annotation", "differ"].map((name) => `--chart-${name}`),
  ...["rain", "heat", "count"].map((name) => `--series-${name}`),
  ...["land", "land-foreign", "water", "coast", "water-label", "river", "salt", "salt-hatch", "border-intl", "border-state", "border-district", "label", "label-minor", "label-halo", "selection", "selection-halo", "hover", "marker", "marker-ring", "place", "nodata", "hillshade-opacity"].map((name) => `--map-${name}`),
  "--shadow-pop", "--shadow-label", "--shadow-sheet", "--grain"
];
const TYPE_SIZES = ["caption", "label", "ui", "ui-lg", "h4", "figcaption", "quote", "body-sm", "body", "lede", "h3", "h2", "h1", "title", "hero", "numeral", "stat"];
const INVARIANT = [
  ...TYPE_SIZES.flatMap((size) => [`--text-${size}`, `--lh-${size}`, `--track-${size}`]),
  ...steps("space", 10), "--space-section",
  "--control-h", "--control-h-touch", "--input-h", "--chip-h", "--search-h", "--segment-h", "--code-w", "--code-h", "--code-w-lg", "--code-h-lg", "--toggle-w", "--toggle-h", "--target", "--appbar-h", "--rail-h",
  "--radius-plate", "--radius-control", "--radius-card", "--radius-sheet", "--radius-pill",
  "--dur-press", "--dur-state", "--dur-panel", "--dur-dip", "--dur-hold", "--dur-oxidise", "--dur-vat", "--dur-vat-delay", "--ease-out", "--ease-inout", "--ease-toggle",
  "--font-headline", "--font-reading", "--font-ui", "--font-code", "--text-zoom",
  "--dye-cloth", "--dye-harda", "--dye-kut", "--dye-leuco", "--dye-indigo", "--dye-madder", "--dye-pink", ...steps("dip", 4), "--photo-ink-1", "--photo-ink-2", "--photo-scrim-start", "--photo-scrim-bottom",
  ...Object.keys(SEMANTIC).map((name) => `--${name}`)
];

const THEMES: Record<string, { index: number; selectors: string[] }> = {
  light: { index: 0, selectors: [":root", ".tscope-light"] },
  dark: { index: 1, selectors: [':root:not([data-theme="light"])', ':root[data-theme="dark"]', ".tscope-dark"] },
  "high contrast light": { index: 2, selectors: [':root:not([data-high-contrast="false"])', ':root[data-high-contrast="true"]', ".tscope-hcl"] },
  "high contrast dark": {
    index: 3,
    selectors: [
      ':root:not([data-high-contrast="false"]):not([data-theme="light"])',
      ':root[data-theme="dark"]:not([data-high-contrast="false"])',
      ':root[data-high-contrast="true"]:not([data-theme="light"])',
      ':root[data-theme="dark"][data-high-contrast="true"]',
      ".tscope-hcd"
    ]
  }
};

function block(css: string, selector: string): Map<string, string> {
  const start = css.indexOf(`${selector} {`);
  if (start < 0 || css.indexOf(`${selector} {`, start + 1) >= 0) throw new Error(`${selector} must open exactly one block`);
  const open = start + selector.length + 2;
  const body = css.slice(open, css.indexOf("}", open));
  return new Map([...body.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)].map((found) => [found[1], found[2].trim()]));
}

const channels = (hex: string) => [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16)).join(" ");

for (const [theme, { index, selectors }] of Object.entries(THEMES)) {
  for (const selector of selectors) {
    test(`${theme} defines every themed token under ${selector}`, () => {
      const declared = block(TOKENS, selector);
      expect(THEMED.filter((name) => !declared.has(name))).toEqual([]);
      for (const [name, values] of Object.entries(SEMANTIC)) expect(declared.get(`--c-${name}`), `${name} in ${selector}`).toBe(channels(values[index]));
    });
  }
}

test("the light root defines every theme-invariant token and the hex alias of every semantic colour", () => {
  const root = block(TOKENS, ":root");
  expect(INVARIANT.filter((name) => !root.has(name))).toEqual([]);
  for (const name of Object.keys(SEMANTIC)) expect(root.get(`--${name}`)).toBe(`rgb(var(--c-${name}))`);
});

test("larger text scales the root by an eighth and every fluid size through --text-zoom", () => {
  expect(block(TOKENS, ':root[data-larger-text="true"]')).toEqual(new Map([["--text-zoom", "1.125"]]));
  expect(TOKENS).toContain(':root[data-larger-text="true"] { font-size: 112.5%; --text-zoom: 1.125; }');
  const root = block(TOKENS, ":root");
  expect(root.get("--text-zoom")).toBe("1");
  for (const size of TYPE_SIZES) {
    const value = root.get(`--text-${size}`) as string;
    if (value.startsWith("clamp(")) expect(value, size).toContain("vw * var(--text-zoom)");
  }
});

test("the tokens hang off the attributes the preferences boot script writes", () => {
  for (const attribute of ['"data-theme",dark?"dark":"light"', '"data-larger-text","true"', '"data-high-contrast","true"', '"data-reduced-motion","true"']) expect(PREFERENCES_BOOT_SCRIPT).toContain(attribute);
  expect(GLOBALS).toContain('@import "./motion.css";');
  expect(MOTION).toContain(':root[data-reduced-motion="true"] *');
  expect(MOTION).toMatch(/@media \(prefers-reduced-motion: reduce\) \{\s*\*,\s*\*::before,\s*\*::after \{\s*animation: none !important;\s*transition: none !important;/);
  expect(THEME_COLOR).toEqual({ light: SEMANTIC.ground[0], dark: SEMANTIC.ground[1] });
});

test("globals.css imports the generated tokens and carries none of the retired look", () => {
  expect(GLOBALS).toContain('@import "./tokens.css";');
  expect(GLOBALS).toContain("--color-*: initial;");
  expect(GLOBALS).toContain("--blur-*: initial;");
  for (const retired of ["oklch(", "grad-", "glass", "ministry", "gold", "backdrop-filter", "--purple", "--font-inter", "--font-jakarta"]) expect(GLOBALS, retired).not.toContain(retired);
});

test("every token the Tailwind config names is defined, and no migration alias is left", () => {
  const root = block(TOKENS, ":root");
  const config = read("tailwind.config.ts");
  const named = [...config.matchAll(/\bc\("([a-z0-9-]+)"/g)].map((found) => found[1]);
  expect(named).toHaveLength(27);
  expect(named.filter((name) => !root.has(`--c-${name}`))).toEqual([]);
  expect(existsSync(join(FRONTEND, "tailwind.migration.ts"))).toBe(false);
  for (const alias of [/legacy/, /\b900:/, /\b600:/, /\bdisplay:/, /[{ ]bold:/, /\bspring:/, /shadow[^}]*\bsm:/]) expect(config, String(alias)).not.toMatch(alias);
  const colours = config.slice(config.indexOf("colors: {"), config.indexOf("fontFamily: {"));
  expect(colours.match(/^\s+(?:"?[a-z-]+"?: |[a-z]+: \{)/gm)?.map((key) => key.trim().replace(/[":{ ]/g, ""))).toEqual(["transparent", "ground", "ink", "indigo", "madder", "turmeric", "error", "warning", "info", "success", "white"]);
});

test("every self-hosted face is named in a font stack, and every script stack opens on a hosted face", () => {
  const hosted = ["latinFonts.ts", "scriptFonts.ts", "readingScriptFonts.ts"].flatMap((file) => [...read("app", file).matchAll(/prop: "font-family", value: "([^"]+)"/g)].map((found) => found[1]));
  const stacks = `${TOKENS}\n${GLOBALS}`;
  expect(new Set(hosted).size).toBe(26);
  for (const family of hosted) expect(stacks, family).toContain(`"${family}"`);
  const scriptStacks = [...TOKENS.matchAll(/--font-[a-z]{4}-(?:reading|ui): "([^"]+)"/g)].map((found) => found[1]);
  expect(scriptStacks).toHaveLength(26);
  expect(scriptStacks.filter((family) => !hosted.includes(family))).toEqual([]);
});

test("each metric-matched fallback face, named after its font's const, is named in the stack after its face", () => {
  const adjusted = [...read("app", "latinFonts.ts").matchAll(/const (\w+) = localFont\(\{[^;]*?adjustFontFallback: "([^"]+)"/g)].map((found) => found[1]);
  expect(adjusted).toEqual(["newsreader", "plexSans"]);
  expect(TOKENS).toMatch(/--font-headline: "Newsreader", "newsreader Fallback",/);
  expect(TOKENS).toMatch(/--font-reading: "Newsreader", [^;]*"newsreader Fallback",/);
  expect(TOKENS).toMatch(/--font-ui: "IBM Plex Sans", [^;]*"plexSans Fallback",/);
  expect(GLOBALS).not.toMatch(/--font-[a-z]+:/);
});

test("the dictation sound bars are a named CSS motion resting at their end state, and the retired springs are gone", () => {
  expect(MOTION).toMatch(/\.motion-sound \{\s*transform: scaleY\(0\.64\);\s*animation: kv-sound var\(--dur-hold\) var\(--ease-inout\) infinite alternate;/);
  const bars = renderToStaticMarkup(createElement(SoundBars));
  expect(bars.match(/class="motion-sound /g)).toHaveLength(5);
  expect([...bars.matchAll(/animation-delay:(\d+)ms/g)].map((found) => Number(found[1]))).toEqual([0, 150, 300, 450, 600]);
  expect(SOUND_BAR_STAGGER_MS).toBe(150);
  expect(existsSync(join(FRONTEND, "components", "guide", "guideMotion.ts"))).toBe(false);
});

test("the five choropleth classes stay five distinct density steps, lowest first, in light and in dark", () => {
  const steps = CHOROPLETH_TONES.map((tone) => /^fill-\[var\(--(density-\d)\)\]$/.exec(tone)?.[1]);
  expect(steps).toEqual(["density-1", "density-2", "density-3", "density-5", "density-6"]);
  for (const step of steps) expect(TOKENS).toContain(`--${step}:`);
});

test("the OS contrast setting gives an app-dark page the high-contrast dark tokens, and Standard opts out", async ({ page }) => {
  const ground = async (attributes: string) => {
    await page.setContent(`<!doctype html><html ${attributes}><head><style>${TOKENS}</style></head><body></body></html>`);
    return page.evaluate(() => ({ ground: getComputedStyle(document.documentElement).getPropertyValue("--c-ground").trim(), scheme: getComputedStyle(document.documentElement).colorScheme }));
  };
  await page.emulateMedia({ colorScheme: "light", contrast: "more" });
  expect(await ground('data-theme="dark"')).toEqual({ ground: "0 0 0", scheme: "dark" });
  expect(await ground('data-theme="dark" data-high-contrast="false"')).toEqual({ ground: "14 18 28", scheme: "dark" });
  expect(await ground('data-theme="light"')).toEqual({ ground: "255 255 255", scheme: "light" });
  await page.emulateMedia({ colorScheme: "dark", contrast: "more" });
  expect(await ground("")).toEqual({ ground: "0 0 0", scheme: "dark" });
  expect(await ground('data-theme="light" data-high-contrast="false"')).toEqual({ ground: "244 245 241", scheme: "light" });
});
