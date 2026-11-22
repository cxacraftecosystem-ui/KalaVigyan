import { inflateRawSync } from "node:zlib";

import type { SourceRecord } from "./answers";

const DOI_PREFIX = "https://doi.org/";
const PDF_HEADER = "%PDF-";
const PDF_END = "%%EOF";
const PDF_URI = /\/URI \(((?:\\.|[^\\)])*)\)/g;
const PDF_PAGE = /\/Type\s*\/Page\b/g;
const ZIP_END = 0x06054b50;
const ZIP_CENTRAL = 0x02014b50;
const ZIP_LOCAL = 0x04034b50;
const STORED = 0;
const DEFLATED = 8;
const XML_ENTITIES: Record<string, string> = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'" };
const HTML_ENTITIES: Record<string, string> = { ...XML_ENTITIES, "&#x27;": "'", "&#39;": "'" };
const HTML_ENTITY = /&(?:amp|lt|gt|quot|apos|#x27|#39);/g;
const HTML_START = /^<!doctype html>/i;
const HTML_END = "</html>";
const DECK_SLIDE = /<section\b/g;
const SLIDE =/^ppt\/slides\/slide\d+\.xml$/;
const SLIDE_RELS = /^ppt\/slides\/_rels\/slide\d+\.xml\.rels$/;
const RELS_TARGET = /Target="(https?:\/\/[^"]+)"/g;
const BIBTEX_LINK: Record<string, string> = { "\\": "%5C", "{": "%7B", "}": "%7D" };

export type CitedSource = Pick<SourceRecord, "title" | "doi" | "url">;

export function referenceLink(source: CitedSource): string | null {
  return source.doi ? `${DOI_PREFIX}${source.doi}` : source.url;
}

function missingLinks(where: string, links: ReadonlySet<string>, sources: readonly CitedSource[]): string[] {
  const missing = sources.map(referenceLink).filter((link): link is string => link !== null && !links.has(link));
  return missing.length > 0 ? [`${where} lacks the link of ${missing.length} of the explainer's sources: ${missing.slice(0, 3).join(", ")}`] : [];
}

export function pdfLinks(file: Buffer): Set<string> {
  const text = file.toString("latin1");
  return new Set([...text.matchAll(PDF_URI)].map((match) => match[1].replace(/\\(.)/g, "$1")));
}

export function pdfProblems(where: string, file: Buffer, sources: readonly CitedSource[]): string[] {
  const text = file.toString("latin1");
  if (!text.startsWith(PDF_HEADER) || !text.trimEnd().endsWith(PDF_END)) return [`${where} is not a whole PDF file`];
  if ((text.match(PDF_PAGE) ?? []).length === 0) return [`${where} holds no page`];
  return missingLinks(where, pdfLinks(file), sources);
}

export function zipEntries(file: Buffer): Map<string, Buffer> {
  const end = file.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  if (end < 0 || file.readUInt32LE(end) !== ZIP_END) throw new Error("no zip directory");
  const count = file.readUInt16LE(end + 10);
  let at = file.readUInt32LE(end + 16);
  const entries = new Map<string, Buffer>();
  for (let n = 0; n < count; n += 1) {
    if (file.readUInt32LE(at) !== ZIP_CENTRAL) throw new Error("a broken zip directory entry");
    const method = file.readUInt16LE(at + 10);
    const size = file.readUInt32LE(at + 20);
    const nameLength = file.readUInt16LE(at + 28);
    const skip = nameLength + file.readUInt16LE(at + 30) + file.readUInt16LE(at + 32);
    const name = file.toString("utf8", at + 46, at + 46 + nameLength);
    entries.set(name, zipData(file, file.readUInt32LE(at + 42), size, method));
    at += 46 + skip;
  }
  return entries;
}

function zipData(file: Buffer, local: number, size: number, method: number): Buffer {
  if (file.readUInt32LE(local) !== ZIP_LOCAL) throw new Error("a broken zip entry");
  const start = local + 30 + file.readUInt16LE(local + 26) + file.readUInt16LE(local + 28);
  const raw = file.subarray(start, start + size);
  if (method === STORED) return raw;
  if (method === DEFLATED) return inflateRawSync(raw);
  throw new Error(`zip method ${method}`);
}

function xmlText(value: string): string {
  return value.replace(/&(?:amp|lt|gt|quot|apos);/g, (entity) => XML_ENTITIES[entity] ?? entity);
}

export function pptxProblems(where: string, file: Buffer, sources: readonly CitedSource[]): string[] {
  let entries: Map<string, Buffer>;
  try {
    entries = zipEntries(file);
  } catch (error) {
    return [`${where} does not open: ${error instanceof Error ? error.message : String(error)}`];
  }
  const slides = [...entries.keys()].filter((name) => SLIDE.test(name));
  if (!entries.has("ppt/presentation.xml") || slides.length === 0) return [`${where} holds no slide`];
  const links = new Set<string>();
  for (const [name, body] of entries) {
    if (SLIDE_RELS.test(name)) for (const match of body.toString("utf8").matchAll(RELS_TARGET)) links.add(xmlText(match[1]));
  }
  return missingLinks(where, links, sources);
}

export function htmlDeckProblems(where: string, file: Buffer, sources: readonly CitedSource[]): string[] {
  const text = file.toString("utf8");
  if (!HTML_START.test(text) || !text.trimEnd().endsWith(HTML_END)) return [`${where} is not a whole HTML file`];
  if ((text.match(DECK_SLIDE) ?? []).length === 0) return [`${where} holds no slide`];
  const shown = text.replace(HTML_ENTITY, (entity) => HTML_ENTITIES[entity] ?? entity);
  const found = new Set(sources.map(referenceLink).filter((link): link is string => link !== null && shown.includes(link)));
  return missingLinks(where, found, sources);
}

function bibtexLink(link: string): string {
  return [...link].map((ch) => BIBTEX_LINK[ch] ?? ch).join("");
}

export function citationFileProblems(format: string, text: string, sources: readonly CitedSource[]): string[] {
  const where = `the ${format} citations`;
  if (format === "json") return cslProblems(where, text, sources);
  const missing = sources.filter((source) => {
    if (format === "ris") return !text.includes(`TI  - ${source.title.trim().split(/\s+/).join(" ")}\r\n`);
    const link = referenceLink(source);
    if (link === null) return false;
    if (format === "bib") return !text.includes(source.doi ? `doi = {${bibtexLink(source.doi)}}` : `url = {${bibtexLink(link)}}`);
    return !text.includes(link);
  });
  return missing.length > 0 ? [`${where} lack ${missing.length} of the explainer's sources: ${missing.slice(0, 3).map((source) => source.title).join("; ")}`] : [];
}

function cslProblems(where: string, text: string, sources: readonly CitedSource[]): string[] {
  let items: unknown;
  try {
    items = JSON.parse(text);
  } catch {
    return [`${where} are not JSON`];
  }
  if (!Array.isArray(items)) return [`${where} are not a list of CSL items`];
  const titles = new Set(items.map((item) => (item && typeof item === "object" ? (item as { title?: unknown }).title : null)));
  const missing = sources.filter((source) => !titles.has(source.title));
  return missing.length > 0 ? [`${where} lack ${missing.length} of the explainer's sources`] : [];
}
