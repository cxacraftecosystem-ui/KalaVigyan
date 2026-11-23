import type { MonographChapterName, MonographComponent, MonographDocument, MonographLayoutEntry, MonographUnit } from "@/lib/monographDocument";
import { placedMastheadPicture } from "@/lib/monographPlacement";
import { hasSentence, nodesText, type MonographSources } from "@/lib/monographRender";

export const COMPONENT_SLOT_PATTERN = /<kv-slot component="([^"]+)"><\/kv-slot>/g;
export const MASTHEAD_PICTURE_KIND = "picture_plate";
export const SOURCES_CHAPTER = "sources";
export const LABEL_MAX_CHARS = 60;
const HEADINGS = new Set(["h2", "h3", "h4"]);

export type UnitRole = "numeral" | "kicker" | "title" | "lede" | "label" | "text";
export type TermGroup = "facts" | "record" | "differ" | "entries";
export type TermsPiece = { kind: "terms"; refs: string[]; group: TermGroup; heading: string | null };
export type PassagePiece = { kind: "unit"; ref: string; role: UnitRole } | { kind: "list"; refs: string[] } | { kind: "paragraph"; refs: string[]; lede: boolean } | TermsPiece;
export const PARAGRAPH_SENTENCES = 3;
export type MarginNote = { ref: string; source: string };
export type Passage = { kind: "passage"; head: boolean; pieces: PassagePiece[]; notes: MarginNote[] };
export type ChapterBlock = Passage | { kind: "component"; label: string } | { kind: "sources"; replaces: string[] };
export type ChapterPlan = { key: string; index: number; number: number | null; label: string; rail: string; blocks: ChapterBlock[] };
export type MastheadPlan = { kicker: string | null; standfirst: string[]; lede: string | null; picture: string | null };
export type LabelMasthead = { kicker: string | null; title: string; terms: string[]; picture: string | null; lede: string[] };
export type PagePlan = { masthead: MastheadPlan; label: LabelMasthead | null; chapters: ChapterPlan[] };

const NO_MASTHEAD: MastheadPlan = { kicker: null, standfirst: [], lede: null, picture: null };
const TERM_TAGS = new Set(["dt", "dd"]);
const GROUP_HEADING_TAG = "h3";
export const RECORD_HEADINGS: ReadonlySet<string> = new Set(["In the record"]);
export const DIFFER_HEADINGS: ReadonlySet<string> = new Set(["Where the sources differ"]);

export type TermRow = { term: string | null; values: string[] };

export function termRows(units: Readonly<Record<string, MonographUnit>>, refs: readonly string[]): TermRow[] {
  const rows: TermRow[] = [];
  for (const ref of refs) {
    const last = rows[rows.length - 1];
    if (units[ref]?.tag === "dt") rows.push({ term: ref, values: [] });
    else if (last) last.values.push(ref);
    else rows.push({ term: null, values: [ref] });
  }
  return rows;
}

export function termGroup(units: Readonly<Record<string, MonographUnit>>, refs: readonly string[], heading: string | null): TermGroup {
  if (heading !== null && DIFFER_HEADINGS.has(heading)) return "differ";
  if (heading !== null && RECORD_HEADINGS.has(heading)) return "record";
  const rows = termRows(units, refs);
  const single = rows.every((row) => row.term !== null && row.values.length === 1);
  return heading === null && single ? "facts" : "entries";
}

export type PassageSegment = { kind: "column"; pieces: PassagePiece[] } | { kind: "group"; piece: TermsPiece };

export function passageSegments(pieces: readonly PassagePiece[]): PassageSegment[] {
  const out: PassageSegment[] = [];
  for (const piece of pieces) {
    const last = out[out.length - 1];
    if (piece.kind === "terms") out.push({ kind: "group", piece });
    else if (last?.kind === "column") last.pieces.push(piece);
    else out.push({ kind: "column", pieces: [piece] });
  }
  return out;
}

export function chapterOrder(layout: readonly MonographLayoutEntry[]): string[] {
  return [...new Set(layout.map((entry) => entry.chapter))];
}

export function nestedComponents(document: MonographDocument): Set<string> {
  const nested = new Set<string>();
  for (const entry of document.content.layout) if (entry.kind === "component" && entry.within) nested.add(entry.ref);
  for (const component of document.content.components) for (const found of placedComponents(document, component.label)) nested.add(found);
  return nested;
}

export function fragmentSlots(html: string): string[] {
  return [...html.matchAll(COMPONENT_SLOT_PATTERN)].map((found) => found[1]);
}

export function specStrings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(specStrings);
  if (value && typeof value === "object") return Object.values(value).flatMap(specStrings);
  return [];
}

export function topLevelEntries(document: MonographDocument, chapter: string, nested: ReadonlySet<string>): MonographLayoutEntry[] {
  return document.content.layout.filter((entry) => entry.chapter === chapter && entry.within === null && !(entry.kind === "component" && nested.has(entry.ref)));
}

export function pagePlan(document: MonographDocument): PagePlan {
  const order = chapterOrder(document.content.layout);
  const nested = nestedComponents(document);
  const [first] = order;
  const opening = first ? topLevelEntries(document, first, nested) : [];
  const label = labelMasthead(document, opening);
  const masthead = first && !label ? mastheadPlan(document, opening) : NO_MASTHEAD;
  const shown = label ? [label.kicker, label.title, ...label.terms, label.picture, ...label.lede] : [masthead.kicker, ...masthead.standfirst, masthead.lede, masthead.picture];
  const taken = new Set(shown.filter((ref): ref is string => ref !== null));
  const chapters = order.map((key, index) => chapterPlan(document, { key, index, nested }, taken));
  return { masthead, label, chapters: chapters.filter((chapter) => chapter.blocks.length > 0 || chapter.index === 0) };
}

export function railChapters(plan: PagePlan): ChapterPlan[] {
  return plan.label ? plan.chapters.filter((chapter) => chapter.number !== null) : plan.chapters;
}

export function labelMasthead(document: MonographDocument, entries: readonly MonographLayoutEntry[]): LabelMasthead | null {
  const units = document.content.units;
  const unitAt = (at: number) => (entries[at]?.kind === "unit" ? units[entries[at].ref] : undefined);
  const titleAt = entries.findIndex((_, at) => unitAt(at)?.tag === "h1");
  if (titleAt < 0) return null;
  const before = unitAt(titleAt - 1);
  const kicker = before?.tag === "p" && !hasSentence(before.nodes) ? entries[titleAt - 1].ref : null;
  let at = titleAt + 1;
  const terms: string[] = [];
  for (; TERM_TAGS.has(unitAt(at)?.tag ?? ""); at += 1) terms.push(entries[at].ref);
  const lede: string[] = [];
  for (; unitAt(at)?.tag === "p" && hasSentence(unitAt(at)?.nodes ?? []); at += 1) lede.push(entries[at].ref);
  const picture = entries.find((entry) => entry.kind === "component" && componentKind(document, entry.ref) === MASTHEAD_PICTURE_KIND)?.ref ?? placedMastheadPicture(document);
  return { kicker, title: entries[titleAt].ref, terms, picture, lede };
}

export function componentKind(document: MonographDocument, label: string): string | null {
  return document.content.components.find((component) => component.label === label)?.kind ?? null;
}

function mastheadPlan(document: MonographDocument, entries: readonly MonographLayoutEntry[]): MastheadPlan {
  const units = document.content.units;
  const lead: string[] = [];
  for (const entry of entries) {
    if (entry.kind !== "unit" || units[entry.ref]?.tag !== "p") break;
    lead.push(entry.ref);
    if (hasSentence(units[entry.ref].nodes)) break;
  }
  const lede = lead.find((ref) => hasSentence(units[ref].nodes)) ?? null;
  const [kicker = null, ...standfirst] = lead.filter((ref) => ref !== lede);
  const next = entries[lead.length];
  const component = next?.kind === "component" ? document.content.components.find((found) => found.label === next.ref) : undefined;
  return { kicker, standfirst, lede, picture: component?.kind === MASTHEAD_PICTURE_KIND ? component.label : null };
}

type ChapterPlace = { key: string; index: number; nested: ReadonlySet<string> };

function chapterPlan(document: MonographDocument, { key, index, nested }: ChapterPlace, taken: ReadonlySet<string>): ChapterPlan {
  const number = index === 0 ? null : index;
  const entries = topLevelEntries(document, key, nested).filter((entry) => !taken.has(entry.ref));
  const blocks: ChapterBlock[] = [];
  let run: string[] = [];
  const flush = () => {
    if (run.length) blocks.push(passage(document, run, { number, head: !blocks.some((b) => b.kind === "passage") }));
    run = [];
  };
  for (const entry of entries) {
    if (entry.kind === "unit") run.push(entry.ref);
    else {
      flush();
      blocks.push({ kind: "component", label: entry.ref });
    }
  }
  flush();
  const named = chapterName(document, key);
  const label = named?.title ?? chapterLabel(document, key, number);
  return { key, index, number, label, rail: named?.rail ?? label, blocks: key === SOURCES_CHAPTER ? withSourceList(document, blocks) : blocks };
}

export function chapterName(document: MonographDocument, key: string): MonographChapterName | undefined {
  if (document.translation) return undefined;
  return document.content.chapters?.find((chapter) => chapter.key === key);
}

export function chapterLabel(document: MonographDocument, key: string, number: number | null): string {
  if (number === null) return keyLabel(key);
  const units = document.content.layout.filter((entry) => entry.chapter === key && entry.kind === "unit").map((entry) => document.content.units[entry.ref]);
  const title = units.findIndex((unit) => unit?.tag === "h2");
  const before = title > 0 ? units[title - 1] : undefined;
  if (before && before.tag === "p" && !isNumeral(before, number) && !hasSentence(before.nodes)) return nodesText(before.nodes).trim();
  if (title >= 0) return nodesText(units[title].nodes).trim();
  return keyLabel(key);
}

function keyLabel(key: string): string {
  return key.charAt(0).toUpperCase() + key.slice(1).replace(/-/g, " ");
}

function isNumeral(unit: MonographUnit, number: number | null): boolean {
  return number !== null && unit.tag === "p" && nodesText(unit.nodes).trim() === String(number);
}

function passage(document: MonographDocument, refs: readonly string[], place: { number: number | null; head: boolean }): Passage {
  const units = document.content.units;
  const notes = refs.flatMap((ref) => {
    const source = noteSource(units[ref], document.content.sources);
    return source ? [{ ref, source }] : [];
  });
  const noted = new Set(notes.map((note) => note.ref));
  const main = refs.filter((ref) => !noted.has(ref));
  const head = place.head && main.some((ref) => units[ref].tag === "h2" || isNumeral(units[ref], place.number));
  return { kind: "passage", head, pieces: pieces(units, main, head ? place.number : null), notes };
}

export function noteSource(unit: MonographUnit | undefined, sources: MonographSources): string | null {
  if (!unit || unit.tag !== "li") return null;
  const [first] = unit.nodes;
  if (typeof first === "string" || first?.m !== "b") return null;
  const number = Number(nodesText(first.c ?? []).trim());
  const found = Object.entries(sources).find(([, source]) => source.number === number);
  return found ? found[0] : null;
}

function pieces(units: Readonly<Record<string, MonographUnit>>, refs: readonly string[], number: number | null): PassagePiece[] {
  const out: PassagePiece[] = [];
  const titleAt = refs.findIndex((ref) => units[ref].tag === "h2");
  refs.forEach((ref, at) => {
    const tag = units[ref].tag;
    const last = out[out.length - 1];
    if (tag === "li" && last?.kind === "list") last.refs.push(ref);
    else if (tag === "li") out.push({ kind: "list", refs: [ref] });
    else if ((tag === "dt" || tag === "dd") && last?.kind === "terms") last.refs.push(ref);
    else if (tag === "dt" || tag === "dd") out.push({ kind: "terms", refs: [ref], group: "entries", heading: null });
    else placeUnit(units, out, ref, unitRole(units, refs, at, { number, titleAt }));
  });
  return groupedTerms(units, out);
}

function placeUnit(units: Readonly<Record<string, MonographUnit>>, out: PassagePiece[], ref: string, role: UnitRole): void {
  const unit = units[ref];
  const last = out[out.length - 1];
  const fullLede = out.some((piece) => piece.kind === "paragraph" && piece.lede && piece.refs.length >= PARAGRAPH_SENTENCES);
  const shown: UnitRole = role === "lede" && fullLede ? "text" : role;
  if (shown === "lede" && last?.kind === "unit" && last.role === "lede") out[out.length - 1] = { kind: "paragraph", refs: [last.ref, ref], lede: true };
  else if (shown === "lede" && last?.kind === "paragraph" && last.lede) last.refs.push(ref);
  else if (shown !== "text" || unit.tag !== "p" || !hasSentence(unit.nodes)) out.push({ kind: "unit", ref, role: shown });
  else if (last?.kind === "paragraph" && !last.lede && last.refs.length < PARAGRAPH_SENTENCES && units[last.refs[0]].field === unit.field) last.refs.push(ref);
  else out.push({ kind: "paragraph", refs: [ref], lede: false });
}

function groupedTerms(units: Readonly<Record<string, MonographUnit>>, found: readonly PassagePiece[]): PassagePiece[] {
  const out: PassagePiece[] = [];
  for (const piece of found) {
    if (piece.kind !== "terms") {
      out.push(piece);
      continue;
    }
    const last = out[out.length - 1];
    const heading = last?.kind === "unit" && units[last.ref].tag === GROUP_HEADING_TAG ? last.ref : null;
    if (heading) out.pop();
    const title = heading ? nodesText(units[heading].nodes).trim() : null;
    out.push({ ...piece, heading, group: termGroup(units, piece.refs, title) });
  }
  return out;
}

function unitRole(units: Readonly<Record<string, MonographUnit>>, refs: readonly string[], at: number, place: { number: number | null; titleAt: number }): UnitRole {
  const unit = units[refs[at]];
  if (unit.tag === "h2") return "title";
  if (unit.tag !== "p") return "text";
  if (isNumeral(unit, place.number)) return "numeral";
  const sentence = hasSentence(unit.nodes);
  if (!sentence && units[refs[at + 1]]?.tag === "h2") return "kicker";
  if (!sentence && nodesText(unit.nodes).trim().length <= LABEL_MAX_CHARS) return "label";
  if (!sentence) return "text";
  const afterTitle = place.titleAt >= 0 && at > place.titleAt && refs.slice(place.titleAt + 1, at).every((ref) => units[ref].tag === "p" && hasSentence(units[ref].nodes));
  return afterTitle && place.number !== null ? "lede" : "text";
}

function withSourceList(document: MonographDocument, blocks: ChapterBlock[]): ChapterBlock[] {
  const units = document.content.units;
  const groups = blocks.findIndex((block) => block.kind === "passage" && !block.head && block.notes.length === 0 && block.pieces.every((p) => p.kind === "unit" && HEADINGS.has(units[p.ref].tag)));
  if (groups >= 0) {
    const replaces = (blocks[groups] as Passage).pieces.map((p) => (p.kind === "unit" ? p.ref : ""));
    return [...blocks.slice(0, groups), { kind: "sources", replaces }, ...blocks.slice(groups + 1)];
  }
  const head = blocks.findIndex((block) => block.kind === "passage" && block.head);
  return [...blocks.slice(0, head + 1), { kind: "sources", replaces: [] }, ...blocks.slice(head + 1)];
}

const SOURCE_LIST_KIND = "source_list";

function listedByComponents(document: MonographDocument): Set<string> {
  const listed = new Set<string>();
  for (const component of document.content.components) {
    const listing = component.kind === SOURCE_LIST_KIND ? document.specs[component.label]?.listing : null;
    const sources = listing && typeof listing === "object" ? (listing as { sources?: unknown }).sources : null;
    if (!Array.isArray(sources)) continue;
    for (const entry of sources) if (entry && typeof entry === "object" && typeof (entry as { key?: unknown }).key === "string") listed.add((entry as { key: string }).key);
  }
  return listed;
}

export function pageSources(document: MonographDocument): string[] {
  const listed = listedByComponents(document);
  return Object.entries(document.content.sources)
    .filter(([key]) => !listed.has(key))
    .sort(([, a], [, b]) => a.number - b.number)
    .map(([key]) => key);
}

export function componentUnits(document: MonographDocument, label: string): string[] {
  const own = document.content.layout.filter((entry) => entry.kind === "unit" && entry.within === label).map((entry) => entry.ref);
  const spec = document.specs[label];
  const named = spec ? specStrings(spec).filter((value) => Object.hasOwn(document.content.units, value)) : [];
  return [...new Set([...own, ...named])];
}

export type ComponentBundle = {
  component: MonographComponent;
  spec: Record<string, unknown> | null;
  fragment: string | null;
  units: Record<string, MonographUnit>;
};

export function placedComponents(document: MonographDocument, label: string): string[] {
  const labels = new Set(document.content.components.map((component) => component.label));
  const spec = document.specs[label];
  const named = spec ? specStrings(spec).filter((value) => value !== label && labels.has(value)) : [];
  const slotted = Object.hasOwn(document.fragments, label) ? fragmentSlots(document.fragments[label]) : [];
  return [...new Set([...named, ...slotted])];
}

export function componentBundles(document: MonographDocument, label: string): Record<string, ComponentBundle> {
  const bundles: Record<string, ComponentBundle> = {};
  const visit = (current: string) => {
    const component = document.content.components.find((found) => found.label === current);
    if (!component || Object.hasOwn(bundles, current)) return;
    const units = Object.fromEntries(componentUnits(document, current).map((ref) => [ref, document.content.units[ref]]));
    const spec = Object.hasOwn(document.specs, current) ? document.specs[current] : null;
    const fragment = Object.hasOwn(document.fragments, current) ? document.fragments[current] : null;
    bundles[current] = { component, spec, fragment, units };
    placedComponents(document, current).forEach(visit);
  };
  visit(label);
  return bundles;
}

export function slotId(label: string): string {
  return `kv-slot-${label.replace(/\//g, "__")}`;
}
