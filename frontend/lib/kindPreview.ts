import type { KindFixture } from "@/lib/kindFixtures";
import { SOURCES_CHAPTER } from "@/lib/monographRenderLayout";
import type { MonographComponent, MonographDocument, MonographLayoutEntry, MonographNode, MonographQuote, MonographSource, MonographUnit } from "@/lib/monographDocument";

export const KIND_PREVIEW_PATH = "/design/kinds";
export const KIND_PREVIEW_TITLE = "Every kind on other crafts";
const UNIT_REF = /^u\d{4}$/;
const BLOCK = 100;
const OPENING = "opening";
const SLUG = "Kind-Fixtures";
const ORIGIN = "https://kalavigyan.vercel.app";

type Built = {
  sources: Record<string, MonographSource>;
  citations: Record<string, MonographQuote[]>;
  units: Record<string, MonographUnit>;
  components: MonographComponent[];
  layout: MonographLayoutEntry[];
  specs: Record<string, Record<string, unknown>>;
};

export function renamedRef(index: number, ref: string): string {
  return `u${String(index * BLOCK + Number(ref.slice(1))).padStart(4, "0")}`;
}

export function renamedSpec(value: unknown, names: Readonly<Record<string, string>>): unknown {
  if (typeof value === "string") return UNIT_REF.test(value) && Object.hasOwn(names, value) ? names[value] : value;
  if (Array.isArray(value)) return value.map((item) => renamedSpec(item, names));
  if (typeof value === "object" && value !== null) return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, renamedSpec(item, names)]));
  return value;
}

const unit = (chapter: string, tag: string, nodes: MonographNode[]): MonographUnit => ({ chapter, tag, field: null, nodes, claimIds: [] });

function citedNodes(text: string, key: string, sources: string[]): MonographNode[] {
  const cut = text.lastIndexOf(" ");
  const [head, last] = cut > 0 ? [text.slice(0, cut + 1), text.slice(cut + 1)] : ["", text];
  return [{ m: "s", c: [head, { m: "cite", key, g: sources, c: [last] }] }];
}

function sourceKey(built: Built, fixture: KindFixture, id: string): string {
  const found = Object.entries(built.sources).find(([, source]) => source.dossierSourceId === `${fixture.craft}:${id}`);
  if (found) return found[0];
  const source = fixture.sources[id];
  const number = Object.keys(built.sources).length + 1;
  built.sources[`g${number}`] = { number, title: source.title, fullTitle: null, publisher: source.publisher, year: source.year, grade: source.reliability, url: source.url, extra: null, dossierSourceId: `${fixture.craft}:${id}` };
  return `g${number}`;
}

function addUnits(built: Built, fixture: KindFixture, chapter: string, names: Readonly<Record<string, string>>) {
  for (const [ref, given] of Object.entries(fixture.units)) {
    const key = names[ref];
    const quotes = given.claims.flatMap((claim) => fixture.facts[claim].quotes.map((quote) => ({ source: sourceKey(built, fixture, quote.source), locator: quote.locator, quote: quote.quote })));
    if (!quotes.length) {
      built.units[key] = unit(chapter, "span", [given.text]);
      continue;
    }
    built.citations[key] = quotes;
    built.units[key] = unit(chapter, "span", citedNodes(given.text, key, [...new Set(quotes.map((quote) => quote.source))]));
  }
}

function component(fixture: KindFixture, chapter: string): MonographComponent {
  return { label: fixture.label, chapter, anchor: `#${fixture.label.replaceAll("/", "--")}`, kind: fixture.kind, title: fixture.title, description: fixture.description, field: fixture.field, fields: [], subjects: [`craft:${fixture.craft}`] };
}

function addFixture(built: Built, fixture: KindFixture, index: number, chapterOf: Map<string, string>) {
  const chapter = fixture.within ? (chapterOf.get(fixture.within) ?? `k${index}`) : `k${index}`;
  chapterOf.set(fixture.label, chapter);
  const names = Object.fromEntries(Object.keys(fixture.units).map((ref) => [ref, renamedRef(index, ref)]));
  addUnits(built, fixture, chapter, names);
  if (!fixture.within) {
    built.units[`${chapter}-title`] = unit(chapter, "h2", [fixture.title]);
    built.units[`${chapter}-kind`] = unit(chapter, "p", [`${fixture.kind.replaceAll("_", " ")} · ${fixture.craftName}`]);
    built.layout.push({ chapter, kind: "unit", ref: `${chapter}-title`, within: null }, { chapter, kind: "unit", ref: `${chapter}-kind`, within: null });
  }
  built.components.push(component(fixture, chapter));
  built.layout.push({ chapter, kind: "component", ref: fixture.label, within: fixture.within });
  built.specs[fixture.label] = renamedSpec(fixture.spec, names) as Record<string, unknown>;
}

function opening(built: Built, fixtures: readonly KindFixture[]) {
  const crafts = [...new Set(fixtures.map((fixture) => fixture.craftName))].join(", ");
  built.units["masthead-kicker"] = unit(OPENING, "p", [{ m: "span", c: ["Fixtures"] }, { m: "span", c: [`${new Set(fixtures.map((fixture) => fixture.kind)).size} kinds`] }]);
  built.units["masthead-title"] = unit(OPENING, "h1", [KIND_PREVIEW_TITLE]);
  built.units["opening-crafts"] = unit(OPENING, "p", [`Drawn for ${crafts}, from their stored facts.`]);
  built.layout.push(...["masthead-kicker", "masthead-title", "opening-crafts"].map((ref) => ({ chapter: OPENING, kind: "unit" as const, ref, within: null })));
}

export function kindPreviewDocument(fixtures: readonly KindFixture[]): MonographDocument {
  const built: Built = { sources: {}, citations: {}, units: {}, components: [], layout: [], specs: {} };
  opening(built, fixtures);
  const chapterOf = new Map<string, string>();
  const ordered = [...fixtures.filter((fixture) => !fixture.within), ...fixtures.filter((fixture) => fixture.within)];
  ordered.forEach((fixture) => addFixture(built, fixture, fixtures.indexOf(fixture) + 1, chapterOf));
  built.units["chapter-sources"] = unit(SOURCES_CHAPTER, "h2", ["Sources"]);
  built.layout.push({ chapter: SOURCES_CHAPTER, kind: "unit", ref: "chapter-sources", within: null });
  return {
    schemaVersion: 1,
    subjectKind: "craft",
    subjectSlug: SLUG,
    language: "en",
    title: KIND_PREVIEW_TITLE,
    version: 1,
    pageUrl: `${ORIGIN}${KIND_PREVIEW_PATH}`,
    shell: null,
    content: { schemaVersion: 1, craftSlug: SLUG, sources: built.sources, citations: built.citations, citationClaims: {}, data: {}, units: built.units, components: built.components, layout: built.layout },
    specs: built.specs,
    fragments: {}
  };
}
