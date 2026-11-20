export type DocumentShape = {
  heading: string;
  chapters: string[];
  railTargets: string[];
  missingTargets: string[];
  citedSentences: number;
};

export type RecordShape = {
  heading: string;
  facts: number;
  start: string;
  questions: number;
  plate: boolean;
  rail: number;
  citeThis: boolean;
};

export type HubShape = {
  heading: string;
  plate: boolean;
  shelves: number;
  plates: number;
  chapters: number;
};

export type EssayShape = {
  question: string;
  lede: number;
  ledeCited: number;
  actions: string[];
};

export const DOCUMENT_ROOT = ".kv-monograph";
export const RECORD_ROOT = '[data-testid="craft-without-monograph"]';
export const HUB_ROOT = '[data-testid="category-hub"]';
export const ESSAY_ROOT = '[data-testid="answer-view"]';
export const RAIL_LINKS = 'nav[aria-label="Chapters"] a[href^="#"]';

export function documentShape(options: { root: string; rail: string }): DocumentShape | null {
  const root = document.querySelector(options.root);
  if (!root) return null;
  const text = (node: Element | null) => (node?.textContent ?? "").replace(/\s+/g, " ").trim();
  const targets = Array.from(root.querySelectorAll(options.rail)).map((link) => decodeURIComponent((link.getAttribute("href") ?? "#").slice(1)));
  const railTargets = [...new Set(targets)];
  return {
    heading: text(root.querySelector("h1")),
    chapters: Array.from(root.querySelectorAll("section.kv-ch")).map((chapter) => chapter.getAttribute("data-label") ?? ""),
    railTargets,
    missingTargets: railTargets.filter((target) => !target || document.getElementById(target) === null),
    citedSentences: root.querySelectorAll("[data-src]").length
  };
}

export function recordShape(options: { root: string; rail: string }): RecordShape | null {
  const root = document.querySelector(options.root);
  if (!root) return null;
  const text = (node: Element | null) => (node?.textContent ?? "").replace(/\s+/g, " ").trim();
  const start = root.querySelector('[data-testid="empty-state"]');
  return {
    heading: text(root.querySelector("h1")),
    facts: root.querySelectorAll('[data-testid="fact-grid"] dt').length,
    start: text(start?.querySelector("h2") ?? null),
    questions: start ? start.querySelectorAll('a[href^="/ask?"]').length : 0,
    plate: root.querySelector('[data-testid="typographic-plate"]') !== null,
    rail: document.querySelectorAll(options.rail).length,
    citeThis: /\bCite this\b/.test(root.textContent ?? "")
  };
}

export function hubShape(rootSelector: string): HubShape | null {
  const root = document.querySelector(rootSelector);
  if (!root) return null;
  return {
    heading: (root.querySelector("h1")?.textContent ?? "").replace(/\s+/g, " ").trim(),
    plate: root.querySelector('[data-testid="hub-plate"]') !== null,
    shelves: root.querySelectorAll('[data-testid="collection-shelf"]').length,
    plates: root.querySelectorAll('[data-testid="collection-plate"], [data-testid="photo-card"]').length,
    chapters: root.querySelectorAll("section.kv-ch").length
  };
}

export function essayShape(rootSelector: string): EssayShape | null {
  const root = document.querySelector(rootSelector);
  if (!root) return null;
  const lede = Array.from(root.querySelectorAll('[data-testid="answer-lede"] [data-testid="answer-sentence"]'));
  const actions = Array.from(root.querySelectorAll('[data-testid="answer-actions"] button'));
  return {
    question: (root.querySelector("h1")?.textContent ?? "").replace(/\s+/g, " ").trim(),
    lede: lede.length,
    ledeCited: lede.filter((sentence) => sentence.querySelector('[data-testid="citation-chip"]') !== null).length,
    actions: actions.map((button) => (button.textContent ?? "").replace(/\s+/g, " ").trim())
  };
}
