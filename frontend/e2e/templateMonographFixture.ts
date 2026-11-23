import type { MonographComponent, MonographDocument, MonographNode, MonographSource, MonographUnit } from "../lib/monographDocument";

import { generatedDocument } from "./generatedMonographFixture";

export const KIN = "bagh-print/kin/related-crafts";
export const SECTION_TITLES = ["Washing", "Printing"];

type Layout = MonographDocument["content"]["layout"][number];

const unit = (chapter: string, tag: string, nodes: MonographNode[]): MonographUnit => ({ chapter, tag, field: null, nodes, claimIds: [] });
const cited = (text: string, last: string, key: string, sources: string[]): MonographNode => ({ m: "s", c: [text, { m: "cite", key, g: sources, c: [last] }] });
const sentence = (chapter: string, key: string, text: string, sources: string[]) => unit(chapter, "p", [cited(`${text} `, "here.", key, sources)]);
const at = (chapter: string, ref: string, within: string | null = null, kind: Layout["kind"] = "unit"): Layout => ({ chapter, kind, ref, within });

function source(number: number, title: string, kind: string, grade: string, publisher: string | null): MonographSource {
  return { number, title, fullTitle: null, publisher, year: 2000 + number, grade, url: `https://example.org/source-${number}`, extra: null, dossierSourceId: null, kind };
}

const SOURCES: Record<string, MonographSource> = {
  g1: source(1, "A registered record", "GI_JOURNAL", "A", "A craft registry"),
  g2: source(2, "A study of mordants", "PAPER", "B", "A journal of dyes"),
  g3: source(3, "A chapter on printed cloth", "BOOK_CHAPTER", "B", "City Museum of Textiles"),
  g4: source(4, "A printers' page", "WEB_PAGE", "C", "A printers' cooperative"),
  g5: source(5, "A compound record", "COMPOUND_RECORD", "A", "A compound library"),
  g6: source(6, "A kin craft's study", "PAPER", "A", "A journal of crafts"),
  g7: source(7, "A kin craft's record", "GI_JOURNAL", "A", "A craft registry")
};

const UNITS: Record<string, MonographUnit> = {
  "chapter-glance": unit("glance", "h2", ["At a glance"]),
  "fact-t": unit("glance", "dt", ["Centres"]),
  "fact-v": unit("glance", "dd", [cited("Two towns on the ", "river", "fact-v", ["g1"])]),
  "chapter-made": unit("made", "h2", ["How it is made"]),
  "made-wash-h": unit("made", "h3", ["Washing"]),
  "made-1": sentence("made", "made-1", "The cloth is washed in running water", ["g3"]),
  "made-2": sentence("made", "made-2", "It dries in the sun between washes", ["g3", "g4"]),
  "made-print-h": unit("made", "h3", ["Printing"]),
  "made-3": sentence("made", "made-3", "The blocks are pressed by hand", ["g5", "g4"]),
  "chapter-kin": unit("kin", "h2", ["Kin crafts and shared science"]),
  "kin-1": sentence("kin", "kin-1", "A kin craft prints with the same blocks", ["g6"]),
  "kin-2": sentence("kin", "kin-2", "A second kin craft dyes in the same bath", ["g7", "g1"])
};

const KIN_COMPONENT: MonographComponent = {
  label: KIN,
  chapter: "kin",
  anchor: "#bagh-print--kin--related-crafts",
  kind: "related_crafts",
  title: "Crafts of the same family",
  description: "The crafts of the same family.",
  field: "OVERVIEW",
  fields: ["OVERVIEW"],
  subjects: ["craft:Bagh-Print"]
};

const KIN_SPEC = {
  head: { title: "Crafts of the same family", family: "Textiles · Hand block printing" },
  crafts: [
    { name: "A first kin craft", path: "/crafts/First-Kin", place: "Rajasthan", gi: true, monograph: true, shares: ["Alum"], sentence: "kin-1" },
    { name: "A second kin craft", path: "/crafts/Second-Kin", place: null, gi: false, monograph: false, shares: [], sentence: "kin-2" }
  ]
};

const CHAPTERS: Layout[] = [
  at("glance", "chapter-glance"),
  at("glance", "fact-t"),
  at("glance", "fact-v"),
  at("made", "chapter-made"),
  at("made", "made-wash-h"),
  at("made", "made-1"),
  at("made", "made-2"),
  at("made", "made-print-h"),
  at("made", "made-3"),
  at("chem", "chapter-chem"),
  at("chem", "chemistry-1"),
  at("kin", "chapter-kin"),
  at("kin", KIN, null, "component"),
  at("kin", "kin-1", KIN),
  at("kin", "kin-2", KIN),
  at("sources", "chapter-sources")
];

export function templateDocument(): MonographDocument {
  const document = generatedDocument();
  const opening = document.content.layout.filter((entry) => entry.chapter === "opening");
  document.content.sources = { ...SOURCES };
  document.content.units = { ...document.content.units, ...UNITS };
  document.content.components = [...document.content.components, KIN_COMPONENT];
  document.content.layout = [...opening, ...CHAPTERS];
  document.specs = { ...document.specs, [KIN]: KIN_SPEC };
  return document;
}

export function withoutKinds(document: MonographDocument): MonographDocument {
  const sources = Object.fromEntries(Object.entries(document.content.sources).map(([key, found]) => [key, { ...found, kind: undefined }]));
  return { ...document, content: { ...document.content, sources } };
}
