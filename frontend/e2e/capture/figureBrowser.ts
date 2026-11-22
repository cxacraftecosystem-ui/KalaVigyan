import type { Declared, SheetEntry, SheetRead } from "./figureCss";

export type DrawnElement = { tag: string; svg: boolean; inner: boolean; box: string; props: Record<string, string> };

type Frame = { rules: CSSRule[]; at: number; sheet: number; chain: string[]; parent: string | null; layer: string };

export function readSheets(kitPath: string): SheetRead {
  const entries: SheetEntry[] = [];
  const layers: string[] = [];
  const sheets = [...document.styleSheets];
  const listed = (sheet: CSSStyleSheet): CSSRule[] => {
    try {
      return [...sheet.cssRules];
    } catch {
      return [];
    }
  };
  const stack: Frame[] = sheets.map((sheet, index) => ({ rules: listed(sheet), at: 0, sheet: index, chain: [], parent: null, layer: "" })).reverse();
  const vars = (style: CSSStyleDeclaration): Declared[] => [...style].filter((name) => name.startsWith("--")).map((name) => [name, style.getPropertyValue(name).trim(), style.getPropertyPriority(name)]);
  const named = (layer: string, name: string) => (layer ? `${layer}.${name}` : name);
  const remember = (name: string) => {
    if (!layers.includes(name)) layers.push(name);
  };
  while (stack.length) {
    const frame = stack[stack.length - 1];
    const rule = frame.rules[frame.at++];
    if (!rule) {
      stack.pop();
      continue;
    }
    const into = (rules: CSSRuleList, chain: string[], parent: string | null, layer: string) => stack.push({ rules: [...rules], at: 0, sheet: frame.sheet, chain, parent, layer });
    const prelude = rule.cssText.slice(0, rule.cssText.indexOf("{")).trim();
    const nested = (text: string) => (frame.parent === null ? text : text.includes("&") ? text.split("&").join(`:is(${frame.parent})`) : `:is(${frame.parent}) ${text}`);
    if (rule instanceof CSSLayerStatementRule) rule.nameList.forEach((name) => remember(named(frame.layer, name)));
    else if (rule instanceof CSSPropertyRule) entries.push({ kind: "property", sheet: frame.sheet, name: rule.name, text: rule.cssText });
    else if (rule instanceof CSSStyleRule) {
      const selector = nested(rule.selectorText);
      entries.push({ kind: "style", sheet: frame.sheet, chain: frame.chain, selector, body: rule.style.cssText, vars: vars(rule.style) });
      if (rule.cssRules.length) into(rule.cssRules, frame.chain, selector, frame.layer);
    } else if (rule.constructor.name === "CSSNestedDeclarations" && frame.parent !== null) {
      const style = (rule as CSSRule & { style: CSSStyleDeclaration }).style;
      entries.push({ kind: "style", sheet: frame.sheet, chain: frame.chain, selector: frame.parent, body: style.cssText, vars: vars(style) });
    } else if (rule instanceof CSSLayerBlockRule) {
      remember(named(frame.layer, rule.name));
      into(rule.cssRules, [...frame.chain, prelude], frame.parent, named(frame.layer, rule.name));
    } else if (rule instanceof CSSImportRule && rule.styleSheet) into(rule.styleSheet.cssRules, [...frame.chain, ...(rule.layerName !== null ? [`@layer ${rule.layerName}`.trim()] : []), ...(rule.media.mediaText ? [`@media ${rule.media.mediaText}`] : [])], frame.parent, frame.layer);
    else if (rule instanceof CSSGroupingRule) into(rule.cssRules, [...frame.chain, prelude], frame.parent, frame.layer);
  }
  const kit = sheets.findIndex((sheet) => sheet.href !== null && new URL(sheet.href).pathname === kitPath);
  return { entries, layers, kit, sheets: sheets.map((sheet) => sheet.href ?? "inline") };
}

export function matchedForms({ scope, forms }: { scope: string; forms: string[] }): { hits: string[]; refused: string[] } {
  const root = document.querySelector(scope);
  if (!root) throw new Error(`No element on the page matches ${scope}`);
  const elements = [root, ...root.querySelectorAll("*")];
  const closed = [...root.querySelectorAll("details")].filter((details) => !details.open);
  const hits = new Set<string>();
  const refused = new Set<string>();
  for (const open of [false, true]) {
    for (const details of closed) details.open = open;
    for (const form of forms.filter((found) => !hits.has(found) && !refused.has(found))) {
      try {
        if (elements.some((element) => element.matches(form))) hits.add(form);
      } catch {
        refused.add(form);
      }
    }
  }
  for (const details of closed) details.open = false;
  return { hits: [...hits], refused: [...refused] };
}

export function outerMarkup(scope: string): string | null {
  return document.querySelector(scope)?.outerHTML ?? null;
}

export function drawnStyles({ scope, vars }: { scope: string; vars: string[] }): DrawnElement[] {
  const root = document.querySelector(scope);
  if (!root) return [];
  const top = root.getBoundingClientRect();
  const elements = [root, ...root.querySelectorAll("*")].filter((element) => element.tagName.toLowerCase() !== "style");
  return elements.map((element) => {
    const style = getComputedStyle(element);
    const box = element.getBoundingClientRect();
    const props: Record<string, string> = {};
    for (const name of [...style].filter((found) => !found.startsWith("--"))) props[name] = style.getPropertyValue(name);
    for (const name of vars) props[name] = style.getPropertyValue(name).trim();
    const edges = element.getClientRects().length ? [box.left - top.left, box.top - top.top, box.width, box.height].map((value) => value.toFixed(2)).join(" ") : "none";
    return { tag: element.tagName.toLowerCase(), svg: element.closest("svg") !== null, inner: element.parentElement?.closest("svg") != null, box: edges, props };
  });
}

export function elementProps(selector: string): Record<string, string> | null {
  const element = document.querySelector(selector);
  if (!element) return null;
  const style = getComputedStyle(element);
  return Object.fromEntries([...style].filter((name) => !name.startsWith("--")).map((name) => [name, style.getPropertyValue(name)]));
}

export function placeProbe({ host, markup, probe }: { host: string; markup: string; probe: string }): boolean {
  const parent = document.querySelector(host);
  const holder = document.createElement("template");
  holder.innerHTML = markup;
  const element = holder.content.firstElementChild;
  if (!parent || !element) return false;
  element.setAttribute(probe, "");
  parent.append(element);
  return true;
}

export function placedOffsets(): Record<string, string> {
  const host = document.getElementById("kv-main");
  if (!host) return {};
  const top = host.getBoundingClientRect().top;
  const placed = [...host.querySelectorAll("[id]")].filter((element) => element.getClientRects().length > 0);
  return Object.fromEntries(placed.map((element) => [element.id, (element.getBoundingClientRect().top - top).toFixed(2)]));
}
