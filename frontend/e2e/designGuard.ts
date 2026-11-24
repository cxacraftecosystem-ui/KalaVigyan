import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

export const GUARD_KINDS = ["retired", "hex", "literal", "alias", "physical", "media", "arbitraryVar"] as const;
export type GuardKind = (typeof GUARD_KINDS)[number];
export type GuardCounts = Partial<Record<GuardKind, number>>;
export type GuardBaseline = Record<string, GuardCounts>;

export const SCANNED_FOLDERS = ["app", "components", "lib"];
export const TOKEN_FILES = new Set(["app/tokens.css"]);
export const VAR_ARBITRARY_FOLDERS = ["components/charts/", "components/map/", "components/cloth/", "components/crafts/"];
export const RETIRED_RAMPS = ["purple", "field", "gold", "ministry", "archive", "errand", "steward", "mango", "evidence", "dye"];
export const STOCK_PALETTES = ["slate", "gray", "zinc", "neutral", "stone", "red", "orange", "amber", "yellow", "lime", "green", "emerald", "teal", "cyan", "sky", "blue", "indigo", "violet", "fuchsia", "pink", "rose"];
export const BREAKPOINTS = [640, 768, 1024, 1200, 1280, 1536];
export const BRAND_MARK_HEX = new Set(["#f25022", "#7fba00", "#00a4ef", "#ffb900", "#4285f4", "#34a853", "#fbbc05", "#ea4335", "#5f01d1"]);

const SOURCE = /\.(ts|tsx|css)$/;
const COLOUR_UTILITIES = [
  "bg", "text", "border", "border-x", "border-y", "border-t", "border-r", "border-b", "border-l", "border-s", "border-e",
  "ring", "ring-offset", "inset-ring", "outline", "divide", "fill", "stroke", "from", "via", "to", "accent", "caret",
  "decoration", "placeholder", "shadow", "inset-shadow", "drop-shadow", "text-shadow"
].join("|");
const SHADE = "(?:50|100|200|300|400|500|600|700|800|900|950)";
const END = "(?:/\\d+)?(?![\\w-])";
const RETIRED_CLASS = new RegExp(
  `(?<![\\w-])(?:${COLOUR_UTILITIES})-(?:(?:${RETIRED_RAMPS.join("|")})-[a-z0-9]+|(?:${STOCK_PALETTES.join("|")})-${SHADE}|black)${END}`,
  "g"
);
const SHADCN_COLOURS = "primary(?:-foreground)?|ring|border|input|background|foreground|popover(?:-foreground)?|muted(?:-foreground)?|destructive(?:-foreground)?";
const ALIAS_COLOURS = `ink(?:-(?:900|700|500|300|body|muted|soft))?|line-200|surface-50|bg-0|progress-(?:track|fill|done)|secondary(?:-foreground)?|accent(?:-foreground)?|white|card|error-(?:100|600)|success-(?:100|600)|${SHADCN_COLOURS}`;
const ALIAS_CLASS = new RegExp(
  [
    `(?<![\\w-])(?:${COLOUR_UTILITIES})-(?:${ALIAS_COLOURS})${END}`,
    `(?<![\\w-])text-(?:xs|sm|base|lg|xl|2xl|3xl|4xl)(?![\\w-])`,
    `(?<![\\w-])font-(?:display|bold|mono)(?![\\w-])`,
    `(?<![\\w-])rounded(?:-(?:[trblse]|[tb][lrse]|s[se]|e[se]))?(?:-(?:sm|md|lg|xl|2xl))?(?![\\w-])(?!=)`,
    `(?<![\\w-])shadow-(?:sm|soft|cta|cta-ministry|glow|glow-soft|md|lg|panel|island)(?![\\w-])`,
    `(?<![\\w-])ease-spring(?![\\w-])`
  ].join("|"),
  "g"
);
const SUFFIX = "-(?![A-Z])[\\w./[\\]%()-]+";
const PHYSICAL_CLASS = new RegExp(
  `(?<![\\w-])(?:-?(?:m[lr]|p[lr]|scroll-m[lr]|scroll-p[lr]|left|right)${SUFFIX}|(?:border-[lr]|rounded-(?:[lr]|[tb][lr]))(?:${SUFFIX})?|(?:text|float|clear)-(?:left|right))(?![\\w-])`,
  "g"
);
const PHYSICAL_CSS = /(?<![\w-])(?:(?:margin|padding|border|inset|scroll-margin|scroll-padding)-(?:left|right)(?:-[a-z]+)?|left|right)\s*:|text-align:\s*(?:left|right)/g;
const MEDIA_RULE = /@media[^{]*\{/g;
const MEDIA_CALL = /matchMedia\(\s*["'`]([^"'`]+)/g;
const MEDIA_VARIANT = /(?<![\w-])(?:min|max)-\[([\d.]+)(px|rem|em)\]:/g;
const MEDIA_WIDTH = /(?:(?:min|max)-width\s*:\s*|width\s*[<>]=?\s*)([\d.]+)(px|rem|em)/g;
const ARBITRARY_VAR = /(?:\[[^\]\s"'`]*var\(--|-\(--[a-z])/g;
const COLOUR_LITERAL = /(?<![\w-])(?:rgba?|hsla?|hwb|oklch|oklab|lab|lch)\(\s*[\d.]/g;
const HEX_COLOUR = /(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![0-9a-zA-Z_-])/g;

const matches = (text: string, pattern: RegExp) => text.match(pattern) ?? [];

export function retiredClasses(text: string): string[] {
  return matches(text, RETIRED_CLASS);
}

export function aliasClasses(text: string): string[] {
  return matches(text, ALIAS_CLASS);
}

export function physicalUtilities(text: string, css = false): string[] {
  return css ? matches(text, PHYSICAL_CSS) : matches(text, PHYSICAL_CLASS);
}

export function colourLiterals(text: string): string[] {
  return matches(text, COLOUR_LITERAL);
}

export function arbitraryVars(text: string): string[] {
  return matches(text, ARBITRARY_VAR);
}

export function hexColours(text: string): string[] {
  return matches(text, HEX_COLOUR).filter((hex) => !BRAND_MARK_HEX.has(hex.toLowerCase()));
}

function onBreakpoint(value: number, unit: string): boolean {
  return unit === "px" && BREAKPOINTS.some((breakpoint) => Math.abs(value - breakpoint) <= 1);
}

function offListWidths(query: string): string[] {
  return [...query.matchAll(MEDIA_WIDTH)].filter((found) => !onBreakpoint(Number(found[1]), found[2])).map((found) => found[0]);
}

export function offListMedia(text: string, css = false): string[] {
  if (css) return [...text.matchAll(MEDIA_RULE)].flatMap((found) => offListWidths(found[0]));
  const variants = [...text.matchAll(MEDIA_VARIANT)].filter((found) => !onBreakpoint(Number(found[1]), found[2])).map((found) => found[0]);
  return [...variants, ...[...text.matchAll(MEDIA_CALL)].flatMap((found) => offListWidths(found[1]))];
}

export function guardCounts(file: string, text: string): GuardCounts {
  const css = file.endsWith(".css");
  const counts: Record<GuardKind, number> = {
    retired: retiredClasses(text).length,
    hex: TOKEN_FILES.has(file) ? 0 : hexColours(text).length,
    literal: TOKEN_FILES.has(file) ? 0 : colourLiterals(text).length,
    alias: aliasClasses(text).length,
    physical: physicalUtilities(text, css).length,
    media: offListMedia(text, css).length,
    arbitraryVar: css || VAR_ARBITRARY_FOLDERS.some((folder) => file.startsWith(folder)) ? 0 : arbitraryVars(text).length
  };
  return Object.fromEntries(GUARD_KINDS.filter((kind) => counts[kind] > 0).map((kind) => [kind, counts[kind]]));
}

function sourceFiles(folder: string): string[] {
  return readdirSync(folder).flatMap((name) => {
    const path = join(folder, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return SOURCE.test(name) ? [path] : [];
  });
}

export type ScannedFile = { key: string; text: string };

export function scannedFiles(frontend: string): ScannedFile[] {
  return SCANNED_FOLDERS.flatMap((folder) => sourceFiles(join(frontend, folder))).map((file) => ({ key: relative(frontend, file).replace(/\\/g, "/"), text: readFileSync(file, "utf8") }));
}

export function scanFrontend(frontend: string): GuardBaseline {
  const counts: GuardBaseline = {};
  for (const { key, text } of scannedFiles(frontend)) {
    const found = guardCounts(key, text);
    if (Object.keys(found).length > 0) counts[key] = found;
  }
  return counts;
}

export function overBaseline(current: GuardBaseline, baseline: GuardBaseline, kind: GuardKind): string[] {
  return Object.entries(current)
    .filter(([file, counts]) => (counts[kind] ?? 0) > (baseline[file]?.[kind] ?? 0))
    .map(([file, counts]) => `${file}: ${counts[kind]} ${kind}, baseline ${baseline[file]?.[kind] ?? 0}`);
}

export function shrunkBaseline(current: GuardBaseline, baseline: GuardBaseline): GuardBaseline {
  const kept: GuardBaseline = {};
  for (const file of Object.keys(baseline).sort()) {
    const counts = Object.fromEntries(
      GUARD_KINDS.map((kind) => [kind, Math.min(current[file]?.[kind] ?? 0, baseline[file][kind] ?? 0)] as const).filter(([, count]) => count > 0)
    );
    if (Object.keys(counts).length > 0) kept[file] = counts;
  }
  return kept;
}

export function baselineText(baseline: GuardBaseline): string {
  const lines = Object.keys(baseline)
    .sort()
    .map((file) => {
      const counts = GUARD_KINDS.filter((kind) => (baseline[file][kind] ?? 0) > 0).map((kind) => `"${kind}": ${baseline[file][kind]}`);
      return `  ${JSON.stringify(file)}: { ${counts.join(", ")} }`;
    });
  return `{\n${lines.join(",\n")}\n}\n`;
}
