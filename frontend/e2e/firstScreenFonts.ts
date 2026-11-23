import type { Page } from "@playwright/test";

import { codeRanges, type DrawnText } from "./latinFaces";

export const LATIN_FAMILIES: ReadonlySet<string> = new Set(["Newsreader", "IBM Plex Sans", "IBM Plex Mono"]);

export type FaceRule = { family: string; style: string; weight: string; range: string; url: string };
export type FirstScreen = { texts: DrawnText[]; rules: FaceRule[]; preloaded: string[] };
export type FaceUse = { url: string; family: string; style: string; samples: string[] };

export async function firstScreen(page: Page): Promise<FirstScreen> {
  return page.evaluate(() => {
    const texts: { family: string; style: string; weight: number; text: string; where: string }[] = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const element = node.parentElement;
      if (!element || !(node.textContent ?? "").trim()) continue;
      const box = element.getBoundingClientRect();
      if (box.width <= 1 || box.height <= 1) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      const shown = [...range.getClientRects()].some((rect) => rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < window.innerHeight && rect.right > 0 && rect.left < window.innerWidth);
      const style = getComputedStyle(element);
      if (!shown || style.visibility !== "visible" || Number(style.opacity) === 0) continue;
      const family = style.fontFamily.split(",")[0].replace(/["']/g, "").trim();
      const where = `${element.tagName.toLowerCase()}.${[...element.classList].join(".")}`;
      texts.push({ family, style: style.fontStyle === "normal" ? "normal" : "italic", weight: Number(style.fontWeight), text: (node.textContent ?? "").trim().slice(0, 60), where });
    }
    const rules: { family: string; style: string; weight: string; range: string; url: string }[] = [];
    for (const sheet of [...document.styleSheets]) {
      let list: CSSRuleList | null = null;
      try {
        list = sheet.cssRules;
      } catch {
        list = null;
      }
      for (const rule of list ? [...list] : []) {
        if (!(rule instanceof CSSFontFaceRule)) continue;
        const declared = rule.style;
        const url = /url\(["']?([^"')]+)["']?\)/.exec(declared.getPropertyValue("src"))?.[1] ?? "";
        rules.push({ family: declared.getPropertyValue("font-family").replace(/["']/g, "").trim(), style: declared.getPropertyValue("font-style") || "normal", weight: declared.getPropertyValue("font-weight") || "400", range: declared.getPropertyValue("unicode-range") || "U+0-10FFFF", url: new URL(url, sheet.href ?? location.href).pathname });
      }
    }
    const preloaded = [...document.querySelectorAll('link[rel="preload"][as="font"]')].map((link) => new URL((link as HTMLLinkElement).href).pathname);
    return { texts, rules, preloaded };
  });
}

function weightGap(declared: string, weight: number): number {
  const [low, high = low] = declared.trim().split(/\s+/).map(Number);
  return weight < low ? low - weight : weight > high ? weight - high : 0;
}

export function ruleFor(rules: readonly FaceRule[], text: Omit<DrawnText, "text">, codepoint: number): FaceRule | null {
  const ranked = rules
    .map((rule, order) => ({ rule, order }))
    .filter(({ rule }) => rule.family === text.family && rule.style === text.style && codeRanges(rule.range).some(([low, high]) => codepoint >= low && codepoint <= high))
    .map(({ rule, order }) => ({ rule, order, gap: weightGap(rule.weight, text.weight) }))
    .sort((left, right) => left.gap - right.gap || right.order - left.order);
  return ranked[0]?.rule ?? null;
}

export function latinUses(screen: FirstScreen): FaceUse[] {
  const uses = new Map<string, FaceUse>();
  for (const text of screen.texts) {
    if (!LATIN_FAMILIES.has(text.family)) continue;
    for (const character of text.text.replace(/\s/g, "")) {
      const rule = ruleFor(screen.rules, text, character.codePointAt(0) ?? 0);
      if (!rule) continue;
      const use = uses.get(rule.url) ?? { url: rule.url, family: rule.family, style: rule.style, samples: [] };
      const sample = `${text.where} ${text.weight}: ${text.text}`;
      if (use.samples.length < 3 && !use.samples.includes(sample)) use.samples.push(sample);
      uses.set(rule.url, use);
    }
  }
  return [...uses.values()].sort((left, right) => left.url.localeCompare(right.url));
}

export function latinPreloads(screen: FirstScreen): string[] {
  const latin = new Set(screen.rules.filter((rule) => LATIN_FAMILIES.has(rule.family)).map((rule) => rule.url));
  return [...new Set(screen.preloaded)].filter((url) => latin.has(url)).sort();
}
