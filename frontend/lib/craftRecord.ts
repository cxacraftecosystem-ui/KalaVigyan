import { askPagePath } from "@/lib/askEntry";
import type { CraftPage, NativeName as RecordName } from "@/lib/craftPageContract";
import { familyLine, plateMaterial } from "@/lib/craftPlate";
import { shownNativeName, type NativeName, type NativeScript } from "@/lib/editorialText";

export const RECORD_KICKER = "Craft";
export const RECORD_PROVENANCE = "From the KalaVigyan craft list";
export const RECORD_HEADING = "What the craft list records";
export const START_BODY = "Choose a question, or ask your own. Each answer is researched and cited as it is written, and becomes part of this page.";
export const QUESTIONS_SHOWN = 3;
export const LIST_SEPARATOR = ", ";

const GI_WORDS = { REGISTERED: "Registered geographical indication", APPLIED: "Geographical indication applied for" } as const;
const NAME_SOURCES = { WIKIDATA: "Wikidata, CC0", DOSSIER: "the KalaVigyan dossier" } as const;
const SCRIPTS: ReadonlySet<string> = new Set<NativeScript>(["Deva", "Beng", "Gujr", "Guru", "Orya", "Taml", "Mlym", "Telu", "Knda", "Aran", "Arab", "Mtei", "Olck"]);

export type RecordFact = { label: string; value: string };
export type RecordQuestion = { question: string; href: string };

export type CraftRecordView = {
  slug: string;
  name: string;
  nativeName: NativeName | null;
  family: string | undefined;
  plateKicker: string | null;
  material: ReturnType<typeof plateMaterial>;
  gi: string | null;
  place: string | null;
  provenance: string[];
  facts: RecordFact[];
  start: string;
  questions: RecordQuestion[];
};

export function recordNativeName(name: RecordName | null): NativeName | null {
  if (!name || !name.script || !SCRIPTS.has(name.script)) return null;
  const sourceKind = name.sourceKind === "WIKIDATA" ? "wikidata" : "dossier";
  return { text: name.text, lang: name.lang, script: name.script as NativeScript, sourceId: name.sourceId, sourceKind, reviewed: name.reviewed };
}

export function languageName(lang: string): string {
  const base = lang.split("-")[0];
  try {
    return new Intl.DisplayNames(["en"], { type: "language" }).of(base) ?? base;
  } catch {
    return base;
  }
}

export function provenanceParts(name: RecordName | null): string[] {
  const shown = shownNativeName(recordNativeName(name));
  if (!shown || !name) return [RECORD_PROVENANCE];
  return [RECORD_PROVENANCE, `${languageName(shown.lang)} name: ${NAME_SOURCES[name.sourceKind]}`];
}

export function recordProvenance(name: RecordName | null): string {
  return provenanceParts(name).join(" · ");
}

export function recordFacts(page: CraftPage): RecordFact[] {
  const { craft } = page;
  const facts: [string, string | null][] = [
    ["Family", craft.familyLabel],
    ["Sub-family", craft.kindLabel],
    ["Home state", craft.stateOfOrigin.join(LIST_SEPARATOR) || null],
    ["Practised in", craft.stateOfPractice.join(LIST_SEPARATOR) || null]
  ];
  return facts.flatMap(([label, value]) => (value && value.trim() ? [{ label, value }] : []));
}

export function recordQuestions(page: CraftPage): RecordQuestion[] {
  const slug = page.craft.slug;
  return page.suggestedQuestions.slice(0, QUESTIONS_SHOWN).map((question) => ({ question, href: askPagePath({ craft: slug, question }) }));
}

export function craftRecordView(page: CraftPage): CraftRecordView {
  const { masthead, craft } = page;
  const family = masthead.kicker.family ?? craft.familyLabel;
  const kind = masthead.kicker.kind ?? craft.kindLabel;
  return {
    slug: craft.slug,
    name: masthead.name,
    nativeName: recordNativeName(masthead.nativeName),
    family: familyLine(family, kind),
    plateKicker: kind,
    material: plateMaterial(family, kind),
    gi: masthead.gi ? GI_WORDS[masthead.gi.status] : null,
    place: masthead.place,
    provenance: provenanceParts(masthead.nativeName),
    facts: recordFacts(page),
    start: `Start the research on ${masthead.name}`,
    questions: recordQuestions(page)
  };
}
