import { readFileSync } from "node:fs";
import { join } from "node:path";

export const AJRAKH_DIR = join(__dirname, "..", "..", "backend", "app", "data", "monographs", "Kutch-Ajrakh");

const COMPONENT_SLOT = /<kv-slot component="([^"]+)"><\/kv-slot>/g;

export function fragmentFile(label: string): string {
  return join(AJRAKH_DIR, "fragments", `${label.replaceAll("/", "__")}.html`);
}

export function assembledTemplate(shell: string = readFileSync(join(AJRAKH_DIR, "template.html"), "utf8")): string {
  return shell.replace(COMPONENT_SLOT, (_, label: string) => assembledTemplate(readFileSync(fragmentFile(label), "utf8")));
}

const VOID = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"]);
const RAW = new Set(["style", "script"]);
const TAG = /<(\/?)([A-Za-z][\w:-]*)((?:\s+[^\s=/>]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*(\/?)>/g;
const ATTRIBUTE = /([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

export type Open = { kind: "open"; tag: string; attrs: Record<string, string>; closed: boolean };
export type Close = { kind: "close"; tag: string };
export type Text = { kind: "text"; text: string };
export type Token = Open | Close | Text;

export function decode(text: string): string {
  return text.replace(/&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z]+);/g, (whole, body: string) => {
    if (body.startsWith("#x")) return String.fromCodePoint(parseInt(body.slice(2), 16));
    if (body.startsWith("#")) return String.fromCodePoint(parseInt(body.slice(1), 10));
    return ENTITIES[body] ?? whole;
  });
}

function attributes(raw: string): Record<string, string> {
  const attrs: Record<string, string> = {};
  for (const found of raw.matchAll(ATTRIBUTE)) attrs[found[1]] = decode(found[2] ?? found[3] ?? found[4] ?? "");
  return attrs;
}

export function tokenize(markup: string): Token[] {
  const tokens: Token[] = [];
  let position = 0;
  TAG.lastIndex = 0;
  for (let found = TAG.exec(markup); found; found = TAG.exec(markup)) {
    if (found.index > position) tokens.push({ kind: "text", text: decode(markup.slice(position, found.index)) });
    const [, closing, tag, raw, selfClosing] = found;
    position = TAG.lastIndex;
    if (closing) {
      tokens.push({ kind: "close", tag });
      continue;
    }
    const closed = Boolean(selfClosing) || VOID.has(tag.toLowerCase());
    tokens.push({ kind: "open", tag, attrs: attributes(raw), closed });
    if (!RAW.has(tag.toLowerCase())) continue;
    const stop = markup.indexOf(`</${tag}>`, position);
    tokens.push({ kind: "text", text: markup.slice(position, stop) });
    position = stop;
    TAG.lastIndex = stop;
  }
  if (position < markup.length) tokens.push({ kind: "text", text: decode(markup.slice(position)) });
  return tokens;
}

export function subtreeEnd(tokens: Token[], start: number): number {
  const open = tokens[start];
  if (open.kind !== "open") throw new Error(`token ${start} opens no element`);
  if (open.closed) return start + 1;
  let depth = 0;
  for (let index = start; index < tokens.length; index++) {
    const token = tokens[index];
    if (token.kind === "open" && !token.closed) depth++;
    if (token.kind === "close" && --depth === 0) return index + 1;
  }
  throw new Error(`<${open.tag}> is never closed`);
}

export type ElementTest = (open: Open) => boolean;

export function anchorTest(anchor: string): ElementTest {
  const byId = /^#([\w-]+)$/.exec(anchor);
  if (byId) return (open) => open.attrs.id === byId[1];
  const byAttribute = /^\[([\w-]+)="([^"]*)"\]$/.exec(anchor);
  if (byAttribute) return (open) => open.attrs[byAttribute[1]] === byAttribute[2];
  throw new Error(`anchor ${anchor} is neither #id nor [attribute="value"]`);
}

export function subtrees(tokens: Token[], test: ElementTest): [number, number][] {
  const found: [number, number][] = [];
  tokens.forEach((token, index) => {
    if (token.kind === "open" && test(token)) found.push([index, subtreeEnd(tokens, index)]);
  });
  return found;
}

export function replaced(tokens: Token[], ranges: [number, number][], by: (range: [number, number]) => Token[]): Token[] {
  const out: Token[] = [];
  let position = 0;
  for (const range of [...ranges].sort((a, b) => a[0] - b[0])) {
    if (range[0] < position) continue;
    out.push(...tokens.slice(position, range[0]), ...by(range));
    position = range[1];
  }
  return [...out, ...tokens.slice(position)];
}

function normalStyle(css: string): string {
  return css
    .split(";")
    .map((part) => part.split(":").map((side) => side.trim()).join(":"))
    .filter((part) => part !== "")
    .join(";");
}

function normalJson(value: string): string {
  if (!/^[[{]/.test(value)) return value;
  try {
    return JSON.stringify(JSON.parse(value));
  } catch {
    return value;
  }
}

function normalValue(name: string, value: string): string {
  if (name === "style") return normalStyle(value);
  if (name === "class") return value.trim().split(/\s+/).join(" ");
  return normalJson(value);
}

export const PICTURE_DELIVERY: ReadonlySet<string> = new Set(["srcset", "sizes"]);

function drawnNames(open: Open): string[] {
  const names = Object.keys(open.attrs);
  return open.tag.toLowerCase() === "img" ? names.filter((name) => !PICTURE_DELIVERY.has(name.toLowerCase())) : names;
}

function openLine(open: Open): string {
  const names = drawnNames(open).sort();
  const shown = names.map((name) => `${name}=${JSON.stringify(normalValue(name, open.attrs[name]))}`);
  return `<${open.tag.toLowerCase()}${shown.length ? " " + shown.join(" ") : ""}>`;
}

export function canonical(tokens: Token[]): string[] {
  const lines: string[] = [];
  let text = "";
  const flush = () => {
    if (text !== "" && !(text.trim() === "" && text.includes("\n"))) lines.push(JSON.stringify(text));
    text = "";
  };
  for (const token of tokens) {
    if (token.kind === "text") {
      text += token.text;
      continue;
    }
    flush();
    if (token.kind === "close") lines.push(`</${token.tag.toLowerCase()}>`);
    else lines.push(openLine(token), ...(token.closed ? [`</${token.tag.toLowerCase()}>`] : []));
  }
  flush();
  return lines;
}
