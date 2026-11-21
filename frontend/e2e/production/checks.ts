import type { UserRole } from "@/lib/types";

export const APPBAR_NAV_MIN_WIDTH = 768;
export const MAIN_NAV_LABEL = "Main";
export const ACCOUNT_LABEL = "Account";
export const MENU_LABEL = "Menu";
export const NO_LAYER_LABEL = "Craft places";
export const CITED_CONTENT = [
  "[data-level]",
  "[data-src]",
  '[data-testid="answer-sentence"]',
  '[data-testid="source-passage"]',
  '[id^="source-"]',
  "blockquote"
].join(", ");
export const OVERFLOW_LIMIT = 12;

const TEXT_LIMIT = 200;
const CONTEXT_CHARS = 30;

export const GAP_COPY_PATTERNS: readonly RegExp[] = [
  /\bcoming soon\b/gi,
  /\bnot (?:yet )?available\b/gi,
  /\b(?:isn['’]t|aren['’]t|wasn['’]t) (?:yet )?available\b/gi,
  /\bnot (?:yet )?built\b/gi,
  /\b(?:isn['’]t|hasn['’]t been|wasn['’]t) built\b/gi,
  /\bnot (?:yet )?implemented\b/gi,
  /\bnot (?:yet )?supported\b/gi,
  /\bunder construction\b/gi,
  /\bwork in progress\b/gi,
  /\bnot (?:yet )?(?:wired|hooked) up\b/gi,
  /\bstay tuned\b/gi,
  /\bin a (?:future|later) (?:release|version|phase|update)\b/gi,
  /\bnot enough (?:cited )?evidence\b/gi,
  /\bnot (?:yet )?curated\b/gi,
  /\byet to be (?:added|built|curated|researched|written)\b/gi,
  /\bnothing (?:here|to show) yet\b/gi
];

export type NavExpectation = { bar: string[]; account: string[]; menu: string[]; depths: string[] };

const LEARNER_BAR = ["Ask", "Crafts", "Map", "Saved"];
const RESEARCHER_TOOLS = ["Give a picture", "Propose knowledge"];
const ACCOUNT_LINKS = ["Connect your AI", "Settings"];
const EVERY_DEPTH = ["Basic", "Detailed", "Expert"];

export const READING_NAV_LABEL = "Reading";
export const READING_BAR = ["Atlas", "Map", "Categories", "Compare"];

export const NAV_BY_ROLE: Partial<Record<UserRole, NavExpectation>> = {
  STUDENT: { bar: LEARNER_BAR, account: ACCOUNT_LINKS, menu: [...LEARNER_BAR, ...ACCOUNT_LINKS], depths: EVERY_DEPTH },
  RESEARCHER: { bar: LEARNER_BAR, account: [...RESEARCHER_TOOLS, ...ACCOUNT_LINKS], menu: [...LEARNER_BAR, ...RESEARCHER_TOOLS, ...ACCOUNT_LINKS], depths: EVERY_DEPTH }
};

export function navExpectation(role: UserRole): NavExpectation | null {
  return NAV_BY_ROLE[role] ?? null;
}

export const ABORTED_REQUESTS: readonly string[] = ["net::ERR_ABORTED", "Load request cancelled", "NS_BINDING_ABORTED"];

export function abortedRequest(failure: string): boolean {
  return ABORTED_REQUESTS.includes(failure);
}

export const WEBKIT_LOAD_FAILED = "TypeError: Load failed";
const WEBKIT_LEFT_FETCH = / due to access control checks\.?\s*$/;
const WEBKIT_UNKNOWN_WEBRTC = "Unrecognized Content-Security-Policy directive 'webrtc'";

export function webkitLeavingNoise(text: string, origin: string): boolean {
  const said = text.trim();
  if (said === WEBKIT_LOAD_FAILED || said.startsWith(WEBKIT_UNKNOWN_WEBRTC)) return true;
  return WEBKIT_LEFT_FETCH.test(said) && said.includes(`${new URL(origin).host}/`);
}

export function clip(text: string, limit = TEXT_LIMIT): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > limit ? `${flat.slice(0, limit - 1)}…` : flat;
}

const ANSI_STYLE = new RegExp(`${String.fromCharCode(27)}\\[[0-9;]*m`, "g");
const ERROR_DETAIL = /^Error:\s/;

export function errorHeadline(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  const lines = message
    .replace(ANSI_STYLE, "")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  const head = lines[0] ?? "";
  const detail = lines.slice(1).find((line) => ERROR_DETAIL.test(line));
  return clip(detail ? `${head} ${detail}` : head);
}

export function gapCopyFindings(text: string): string[] {
  const found = new Set<string>();
  for (const pattern of GAP_COPY_PATTERNS) {
    for (const match of text.matchAll(pattern)) {
      const before = text.slice(Math.max(0, match.index - CONTEXT_CHARS), match.index);
      const after = text.slice(match.index + match[0].length, match.index + match[0].length + CONTEXT_CHARS);
      const head = match.index > CONTEXT_CHARS ? before.replace(/^\S*\s?/, "") : before;
      const tail = match.index + match[0].length + CONTEXT_CHARS < text.length ? after.replace(/\s?\S*$/, "") : after;
      found.add(clip(`${head}${match[0]}${tail}`));
    }
  }
  return [...found];
}

export function labelProblems(where: string, expected: readonly string[], actual: readonly string[]): string[] {
  const shown = actual.map((label) => label.replace(/\s+/g, " ").trim()).filter(Boolean);
  const same = shown.length === expected.length && expected.every((label, index) => label === shown[index]);
  if (same) return [];
  return [`${where} shows [${shown.join(", ")}]; this role should see [${expected.join(", ")}]`];
}

export type OverviewServed = { curated: boolean; version: number | null; coverage: string | null; lede: number; keyFacts: number };
export type OverviewShown = { lede: number; keyFacts: number };

export function overviewNote(served: OverviewServed): string {
  return served.curated ? `curated: version ${served.version}, ${served.coverage} coverage` : "not curated";
}

export function curatedOverviewProblems(served: OverviewServed, shown: OverviewShown): string[] {
  if (!served.curated) return [];
  const problems: string[] = [];
  if (served.lede === 0) problems.push("the curated page serves no lede");
  else if (shown.lede !== served.lede) problems.push(`the lede shows ${shown.lede} of its ${served.lede} sentences`);
  if (served.keyFacts === 0) problems.push("the curated page serves no key facts");
  else if (shown.keyFacts !== served.keyFacts) problems.push(`the key facts show ${shown.keyFacts} of ${served.keyFacts}`);
  return problems;
}
