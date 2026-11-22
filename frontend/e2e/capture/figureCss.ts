export type Declared = [name: string, value: string, priority: string];
export type StyleEntry = { kind: "style"; sheet: number; chain: string[]; selector: string; body: string; vars: Declared[] };
export type PropertyEntry = { kind: "property"; sheet: number; name: string; text: string };
export type SheetEntry = StyleEntry | PropertyEntry;
export type SheetRead = { entries: SheetEntry[]; layers: string[]; kit: number; sheets: string[] };
export type PlacedRule = { chain: string[]; text: string };

const STATES = new Set(["hover", "focus", "focus-visible", "focus-within", "active", "visited", "target", "target-within", "user-invalid", "user-valid"]);
const LEGACY_ELEMENTS = new Set(["before", "after", "first-line", "first-letter"]);
const COMBINATOR = /[\s>+~]/;
const ROOT_START = /^(?::root|html)(?![\w-])/;
const VAR_NAME = /var\(\s*(--[A-Za-z0-9_-]+)/g;
const DECLARED_NAME = /(?:^|[{;\s])(--[A-Za-z0-9_-]+)\s*:/g;
const STRUCTURAL = /:(?:first-child|last-child|only-child|nth-child|nth-last-child|first-of-type|last-of-type|only-of-type|nth-of-type|nth-last-of-type|empty)\b|[+~]/;
const QUOTES = new Set(['"', "'"]);
const LAYER = "@layer ";

type Pseudo = { start: number; end: number; element: boolean; state: boolean };

function closing(text: string, at: number): number {
  const open = text[at];
  const close = open === "(" ? ")" : open === "[" ? "]" : open;
  let depth = 0;
  for (let index = at; index < text.length; index++) {
    const char = text[index];
    if (char === "\\") index++;
    else if (QUOTES.has(open)) {
      if (index > at && char === close) return index;
    } else if (QUOTES.has(char)) index = closing(text, index);
    else if (char === open) depth++;
    else if (char === close && --depth === 0) return index;
  }
  throw new Error(`The selector ${text} does not close the ${open} at ${at}`);
}

function skipped(text: string, at: number): number {
  const char = text[at];
  if (char === "\\") return at + 1;
  return char === "(" || char === "[" || QUOTES.has(char) ? closing(text, at) : at;
}

export function complexSelectors(list: string): string[] {
  const parts: string[] = [];
  let start = 0;
  for (let at = 0; at < list.length; at = skipped(list, at) + 1) {
    if (list[at] !== ",") continue;
    parts.push(list.slice(start, at).trim());
    start = at + 1;
  }
  return [...parts, list.slice(start).trim()].filter(Boolean);
}

function pseudoAt(text: string, at: number): Pseudo {
  const double = text[at + 1] === ":";
  const nameStart = at + (double ? 2 : 1);
  let end = nameStart;
  while (end < text.length && /[\w-]/.test(text[end])) end++;
  const name = text.slice(nameStart, end).toLowerCase();
  if (text[end] === "(") end = closing(text, end) + 1;
  return { start: at, end, element: double || LEGACY_ELEMENTS.has(name), state: !double && STATES.has(name) };
}

function topPseudos(selector: string): Pseudo[] {
  const found: Pseudo[] = [];
  for (let at = 0; at < selector.length; at++) {
    if (selector[at] !== ":") {
      at = skipped(selector, at);
      continue;
    }
    const pseudo = pseudoAt(selector, at);
    found.push(pseudo);
    at = pseudo.end - 1;
  }
  return found;
}

function opensCompound(text: string): boolean {
  return text === "" || COMBINATOR.test(text[text.length - 1]);
}

function firstCombinator(selector: string): number {
  for (let at = 0; at < selector.length; at = skipped(selector, at) + 1) if (COMBINATOR.test(selector[at])) return at;
  return -1;
}

export function isRootCompound(selector: string): boolean {
  return ROOT_START.test(selector) && firstCombinator(selector) < 0;
}

function subjectOf(selector: string): string {
  const at = ROOT_START.test(selector) ? firstCombinator(selector) : -1;
  return at < 0 ? selector : selector.slice(at).replace(/^[\s>+~]+/, "");
}

export function matchingForm(selector: string): string {
  const subject = subjectOf(selector.trim());
  let out = "";
  let from = 0;
  for (const pseudo of topPseudos(subject)) {
    if (!pseudo.element && !pseudo.state) continue;
    out += subject.slice(from, pseudo.start);
    if (opensCompound(out)) out += "*";
    from = pseudo.end;
  }
  out = (out + subject.slice(from)).trim();
  return opensCompound(out) ? `${out}*` : out;
}

export function whereScope(scope: string): string {
  return `:where(${scope}, ${scope} *)`;
}

export function scopedSelector(selector: string, scope: string): string {
  const element = topPseudos(selector).find((pseudo) => pseudo.element);
  const at = element ? element.start : selector.length;
  const base = selector.slice(0, at).trim();
  return `:is(${opensCompound(base) ? `${base}*` : base})${whereScope(scope)}${selector.slice(at)}`;
}

export function rootScopedSelector(selector: string, scope: string): string {
  return `:is(${selector}) :where(${scope})`;
}

export function varNames(text: string): string[] {
  return [...new Set([...text.matchAll(VAR_NAME)].map((found) => found[1]))];
}

export function nestedCss(rules: readonly PlacedRule[]): string {
  const lines: string[] = [];
  let open: string[] = [];
  for (const rule of rules) {
    let shared = 0;
    while (shared < open.length && shared < rule.chain.length && open[shared] === rule.chain[shared]) shared++;
    for (let depth = open.length; depth > shared; depth--) lines.push("}");
    for (const prelude of rule.chain.slice(shared)) lines.push(`${prelude} {`);
    lines.push(rule.text);
    open = rule.chain;
  }
  for (let depth = open.length; depth > 0; depth--) lines.push("}");
  return lines.join("\n");
}

export function selectorForms(read: SheetRead): string[] {
  const forms = read.entries.flatMap((entry) => (entry.kind === "style" && entry.sheet !== read.kit ? complexSelectors(entry.selector).map(matchingForm) : []));
  return [...new Set(forms)];
}

export function layerOrder(rules: readonly PlacedRule[], layers: readonly string[]): string {
  const used = new Set(rules.flatMap((rule) => rule.chain.filter((prelude) => prelude.startsWith(LAYER)).slice(0, 1).map((prelude) => prelude.slice(LAYER.length).trim())));
  const ordered = layers.filter((name) => used.has(name));
  return ordered.length ? `@layer ${ordered.join(", ")};` : "";
}

export function structuralSelectors(rules: readonly PlacedRule[], scope: string): string[] {
  const where = whereScope(scope);
  return rules.map((rule) => rule.text.slice(0, rule.text.indexOf(" {"))).filter((selector) => STRUCTURAL.test(selector.split(where).join("")));
}

export function declaredNames(text: string): string[] {
  return [...new Set([...text.matchAll(DECLARED_NAME)].map((found) => found[1]))];
}
