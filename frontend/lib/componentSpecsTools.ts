import type { MonographNode } from "@/lib/monographDocument";
import { monographNodeShape } from "@/lib/monographDocumentShape";
import { boolean, integer, list, matching, object, oneOf, optional, parseShape, ShapeError, text, type Shape } from "@/lib/shape";
import { UNIT_REF } from "@/lib/unitIds";

export const TOOL_KINDS = ["explainer", "quiz", "ask_next", "language_switch", "reading_level", "generator"] as const;
export type ToolKind = (typeof TOOL_KINDS)[number];

const UNIT_REF_SHAPE = matching(UNIT_REF, "a unit ref");
const LABEL = matching(/^[a-z0-9]+(-[a-z0-9]+)*(\/[a-z0-9]+(-[a-z0-9]+)*){2,}$/, "a component label");
const LANG = matching(/^[a-z]{2,3}$/, "a language code");
const DIRECTION = oneOf(["ltr", "rtl"] as const);
const NODES = list(monographNodeShape, 1);

export type QuoteCard = { source: string; byline: string; quote?: string; quoteUnit?: string; locator: string; keyed: boolean };
export type ExplainerSpec = { kicker: string; title: string; sentence: string; keys: string[]; cardsLabel: string; cards: QuoteCard[] };
export type QuizChoice = { term: string; right: boolean; sentence: MonographNode[] };
export type QuizQuestion = { before: string; after: string; cite: { key: string; sources: string[] }; choices: QuizChoice[] };
export type QuizSpec = { title: string; kicker: string; dek: string; score: string; status: string; nextLabel: string; questions: QuizQuestion[] };
export type AskNextSpec = { craft: string; action: string; questions: string[] };
export type GradeCount = { grade: "A" | "B" | "C" | "D"; count: number };
export type PanelProvenance = {
  items: string[];
  reliability: { label: string; grades: GradeCount[] };
  monograph: { text: string; href: string };
  answered: string;
  listen: { label: string; minutes: number; unit: string };
};
export type MarginPlate = { src: string; width: number; height: number; alt: string; caption: MonographNode[]; credit: string };
export type LanguagePanel = {
  lang: string;
  direction: "ltr" | "rtl";
  provenance: PanelProvenance;
  lede: MonographNode[];
  actions: { save: string; cite: string };
  section: { kind: string; title: string; body: MonographNode[] };
  figure?: string;
  notes: string[];
  plate?: MarginPlate;
};
export type LanguageOption = { lang: string; name: string; direction: "ltr" | "rtl"; status: string };
export type LanguageSwitchSpec = { label: string; options: LanguageOption[]; english: string; panels: LanguagePanel[] };
export type ReadingLevelSpec = { level: string; summary: string; detail: string; title: string; lede: string };
export type GeneratorSection = { number: number; title?: string; titleUnit?: string; kind: string; text?: MonographNode[]; textUnit?: string; media: string[]; split: boolean };
export type GeneratorSpec = {
  stage: { state: string; detail: string };
  switchLabel: string;
  switchDetail: string;
  replay: string;
  status: string;
  sections: GeneratorSection[];
  film?: string;
  railTitle: string;
  railDetail: string;
  jobs: { title: string; state: string }[];
};

function exactlyOne<T>(inner: Shape<T>, pairs: readonly (readonly [keyof T, keyof T])[]): Shape<T> {
  return {
    expected: inner.expected,
    parse(value, path) {
      const parsed = inner.parse(value, path);
      for (const [a, b] of pairs) if ((parsed[a] === undefined) === (parsed[b] === undefined)) throw new ShapeError(`${path}.${String(a)}`, `${String(a)} or ${String(b)}, exactly one`);
      return parsed;
    }
  };
}

const quoteCardShape = exactlyOne(
  object<QuoteCard>({ source: text, byline: text, quote: optional(text), quoteUnit: optional(UNIT_REF_SHAPE), locator: text, keyed: boolean }),
  [["quote", "quoteUnit"]]
);

export const explainerSpecShape: Shape<ExplainerSpec> = object<ExplainerSpec>({
  kicker: UNIT_REF_SHAPE,
  title: UNIT_REF_SHAPE,
  sentence: UNIT_REF_SHAPE,
  keys: list(UNIT_REF_SHAPE, 1),
  cardsLabel: text,
  cards: list(quoteCardShape, 1)
});

const quizQuestionShape: Shape<QuizQuestion> = {
  expected: "a quiz question",
  parse(value, path) {
    const parsed = object<QuizQuestion>({
      before: text,
      after: text,
      cite: object({ key: text, sources: list(text, 1) }),
      choices: list(object<QuizChoice>({ term: text, right: boolean, sentence: NODES }), 2)
    }).parse(value, path);
    if (parsed.choices.filter((choice) => choice.right).length !== 1) throw new ShapeError(`${path}.choices`, "exactly one right choice");
    return parsed;
  }
};

export const quizSpecShape: Shape<QuizSpec> = object<QuizSpec>({
  title: UNIT_REF_SHAPE,
  kicker: text,
  dek: UNIT_REF_SHAPE,
  score: UNIT_REF_SHAPE,
  status: UNIT_REF_SHAPE,
  nextLabel: text,
  questions: list(quizQuestionShape, 1)
});

export const askNextSpecShape: Shape<AskNextSpec> = object<AskNextSpec>({ craft: matching(/^[A-Za-z0-9-]+$/, "a craft slug"), action: text, questions: list(text, 1) });

const provenanceShape: Shape<PanelProvenance> = object<PanelProvenance>({
  items: list(text, 1),
  reliability: object({ label: text, grades: list(object<GradeCount>({ grade: oneOf(["A", "B", "C", "D"] as const), count: integer }), 1) }),
  monograph: object({ text, href: matching(/^#[A-Za-z][\w-]*$/, "an anchor on the page") }),
  answered: text,
  listen: object({ label: text, minutes: integer, unit: text })
});

const plateShape: Shape<MarginPlate> = object<MarginPlate>({ src: matching(/^\/[\w./-]+$/, "a path on this site"), width: integer, height: integer, alt: text, caption: NODES, credit: UNIT_REF_SHAPE });

const panelShape: Shape<LanguagePanel> = object<LanguagePanel>({
  lang: LANG,
  direction: DIRECTION,
  provenance: provenanceShape,
  lede: NODES,
  actions: object({ save: text, cite: text }),
  section: object({ kind: text, title: UNIT_REF_SHAPE, body: NODES }),
  figure: optional(LABEL),
  notes: list(UNIT_REF_SHAPE),
  plate: optional(plateShape)
});

export const languageSwitchSpecShape: Shape<LanguageSwitchSpec> = {
  expected: "a language switch",
  parse(value, path) {
    const parsed = object<LanguageSwitchSpec>({
      label: text,
      options: list(object<LanguageOption>({ lang: LANG, name: text, direction: DIRECTION, status: text }), 2),
      english: UNIT_REF_SHAPE,
      panels: list(panelShape)
    }).parse(value, path);
    const others = parsed.options.slice(1).map((option) => option.lang).join();
    if (parsed.panels.map((panel) => panel.lang).join() !== others) throw new ShapeError(`${path}.panels`, "one panel for each language after the first");
    return parsed;
  }
};

export const readingLevelSpecShape: Shape<ReadingLevelSpec> = object<ReadingLevelSpec>({ level: matching(/^[a-z]+$/, "a level"), summary: text, detail: text, title: UNIT_REF_SHAPE, lede: UNIT_REF_SHAPE });

const sectionShape = exactlyOne(
  object<GeneratorSection>({
    number: integer,
    title: optional(text),
    titleUnit: optional(UNIT_REF_SHAPE),
    kind: text,
    text: optional(NODES),
    textUnit: optional(UNIT_REF_SHAPE),
    media: list(LABEL),
    split: boolean
  }),
  [["title", "titleUnit"], ["text", "textUnit"]]
);

export const generatorSpecShape: Shape<GeneratorSpec> = object<GeneratorSpec>({
  stage: object({ state: text, detail: text }),
  switchLabel: text,
  switchDetail: text,
  replay: text,
  status: text,
  sections: list(sectionShape, 1),
  film: optional(LABEL),
  railTitle: UNIT_REF_SHAPE,
  railDetail: UNIT_REF_SHAPE,
  jobs: list(object({ title: text, state: text }))
});

export const TOOL_SPEC_SHAPES: { readonly [K in ToolKind]: Shape<unknown> } = {
  explainer: explainerSpecShape,
  quiz: quizSpecShape,
  ask_next: askNextSpecShape,
  language_switch: languageSwitchSpecShape,
  reading_level: readingLevelSpecShape,
  generator: generatorSpecShape
};

export function parseToolSpec<T>(shape: Shape<T>, spec: Record<string, unknown>): T {
  return parseShape(shape, spec);
}

