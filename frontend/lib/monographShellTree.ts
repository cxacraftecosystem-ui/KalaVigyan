export type ShellAttributes = Readonly<Record<string, string>>;

export type ShellNode =
  | { kind: "text"; text: string }
  | { kind: "slot"; label: string }
  | { kind: "element"; tag: string; attrs: ShellAttributes; children: ShellNode[] }
  | { kind: "held"; tag: string; attrs: ShellAttributes; html: string };

export const SHELL_SLOT_TAG = "kv-slot";
export const SHELL_SLOT_ATTRIBUTE = "component";

const TAG_SOURCE = String.raw`<!--[\s\S]*?-->|<(\/?)([A-Za-z][\w:-]*)((?:\s+[^\s"'>/=]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>\x60]+))?)*)\s*(\/?)>`;
const ATTRIBUTE = /([^\s"'>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
const COMMENT = /<!--[\s\S]*?-->/g;
const ENTITY = /&(#x[0-9a-fA-F]+|#\d+|[A-Za-z]+);/g;
const VOID = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"]);
const RAW_TEXT = new Set(["script", "style"]);
const NAMED: Readonly<Record<string, string>> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: " ",
  ensp: " ",
  emsp: " ",
  thinsp: " ",
  ndash: "–",
  mdash: "—",
  lsquo: "‘",
  rsquo: "’",
  ldquo: "“",
  rdquo: "”",
  hellip: "…",
  middot: "·",
  times: "×",
  minus: "−",
  deg: "°",
  rarr: "→",
  larr: "←",
  bull: "•",
  shy: "­"
};

type ShellElement = {
  tag: string;
  attrs: ShellAttributes;
  start: number;
  openEnd: number;
  closeStart: number;
  end: number;
  children: ShellElement[];
};

export class ShellParseError extends Error {}

export function decodeShellText(text: string): string {
  return text.replace(ENTITY, (whole, body: string) => {
    if (body.startsWith("#x")) return String.fromCodePoint(parseInt(body.slice(2), 16));
    if (body.startsWith("#")) return String.fromCodePoint(parseInt(body.slice(1), 10));
    const named = NAMED[body];
    if (named === undefined) throw new ShellParseError(`The shell names an entity it cannot read: ${whole}`);
    return named;
  });
}

export function shellAttributes(raw: string): ShellAttributes {
  const attrs: Record<string, string> = {};
  for (const found of raw.matchAll(ATTRIBUTE)) attrs[found[1]] = decodeShellText(found[2] ?? found[3] ?? found[4] ?? "");
  return attrs;
}

function opened(match: RegExpExecArray): ShellElement {
  const end = match.index + match[0].length;
  return { tag: match[2], attrs: shellAttributes(match[3]), start: match.index, openEnd: end, closeStart: end, end, children: [] };
}

function rawTextEnd(html: string, element: ShellElement): number {
  const close = html.indexOf(`</${element.tag}`, element.openEnd);
  const end = close < 0 ? -1 : html.indexOf(">", close);
  if (end < 0) throw new ShellParseError(`The shell never closes <${element.tag}>`);
  element.closeStart = close;
  element.end = end + 1;
  return element.end;
}

function closeElement(open: ShellElement[], match: RegExpExecArray): void {
  const element = open.pop();
  if (!element || element.tag !== match[2]) throw new ShellParseError(`The shell closes <${match[2]}> while <${element?.tag ?? "nothing"}> is open`);
  element.closeStart = match.index;
  element.end = match.index + match[0].length;
}

function shellElements(html: string): ShellElement[] {
  const roots: ShellElement[] = [];
  const open: ShellElement[] = [];
  const tags = new RegExp(TAG_SOURCE, "g");
  for (let match = tags.exec(html); match; match = tags.exec(html)) {
    if (match[2] === undefined) continue;
    if (match[1] === "/") {
      closeElement(open, match);
      continue;
    }
    const element = opened(match);
    (open.at(-1)?.children ?? roots).push(element);
    if (match[4] === "/" || VOID.has(element.tag.toLowerCase())) continue;
    if (RAW_TEXT.has(element.tag.toLowerCase())) tags.lastIndex = rawTextEnd(html, element);
    else open.push(element);
  }
  if (open.length) throw new ShellParseError(`The shell never closes <${open[open.length - 1].tag}>`);
  return roots;
}

function slotLabel(element: ShellElement, natives: ReadonlySet<string>): string | null {
  const label = element.attrs[SHELL_SLOT_ATTRIBUTE];
  return element.tag === SHELL_SLOT_TAG && label !== undefined && natives.has(label) ? label : null;
}

function holders(roots: readonly ShellElement[], natives: ReadonlySet<string>): Set<ShellElement> {
  const holding = new Set<ShellElement>();
  const visit = (element: ShellElement): boolean => {
    const inside = element.children.map(visit).some(Boolean);
    const held = inside || slotLabel(element, natives) !== null;
    if (held) holding.add(element);
    return held;
  };
  roots.forEach(visit);
  return holding;
}

type Plan = { html: string; natives: ReadonlySet<string>; holding: ReadonlySet<ShellElement> };

function pushText(nodes: ShellNode[], raw: string): void {
  const text = decodeShellText(raw.replace(COMMENT, ""));
  if (text) nodes.push({ kind: "text", text });
}

function nodeOf(plan: Plan, element: ShellElement): ShellNode {
  const label = slotLabel(element, plan.natives);
  if (label !== null) return { kind: "slot", label };
  if (plan.holding.has(element)) return { kind: "element", tag: element.tag, attrs: element.attrs, children: nodesBetween(plan, [element.openEnd, element.closeStart], element.children) };
  if (element.openEnd === element.end) return { kind: "element", tag: element.tag, attrs: element.attrs, children: [] };
  return { kind: "held", tag: element.tag, attrs: element.attrs, html: plan.html.slice(element.openEnd, element.closeStart) };
}

function nodesBetween(plan: Plan, [from, to]: [number, number], children: readonly ShellElement[]): ShellNode[] {
  const nodes: ShellNode[] = [];
  let at = from;
  for (const child of children) {
    pushText(nodes, plan.html.slice(at, child.start));
    nodes.push(nodeOf(plan, child));
    at = child.end;
  }
  pushText(nodes, plan.html.slice(at, to));
  return nodes;
}

export function shellTree(html: string, natives: ReadonlySet<string>): ShellNode[] {
  const roots = shellElements(html);
  return nodesBetween({ html, natives, holding: holders(roots, natives) }, [0, html.length], roots);
}

export function shellSlots(nodes: readonly ShellNode[]): string[] {
  return nodes.flatMap((node) => {
    if (node.kind === "slot") return [node.label];
    return node.kind === "element" ? shellSlots(node.children) : [];
  });
}
