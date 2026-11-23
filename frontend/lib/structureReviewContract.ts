import { boolean, integer, list, nullable, object, oneOf, tagged, text, type Shape } from "@/lib/shape";

export const STRUCTURE_KINDS = [
  "STAGE_AFTER",
  "STAGE_WHY",
  "NATIVE_NAME",
  "REACTION",
  "BOTANICAL_NAME",
  "GLOSSARY_TERM",
  "CONFLICT",
  "OPEN_QUESTION",
  "GI_RECORD",
  "ALTERNATIVE"
] as const;

export type StructureKind = (typeof STRUCTURE_KINDS)[number];
export type StructureSpecies = { name: string; formula: string | null };
export type StructureCheck = { check: string; passed: boolean; reasons: string[] };

export type StageAfterEntry = { kind: "STAGE_AFTER"; stageKey: string; text: string; colours: string[] };
export type StageWhyEntry = { kind: "STAGE_WHY"; stageKey: string };
export type NativeNameEntry = { kind: "NATIVE_NAME"; text: string; language: string; script: string | null };
export type ReactionEntry = {
  kind: "REACTION";
  reactionKind: string;
  stageKey: string | null;
  reactants: StructureSpecies[];
  products: StructureSpecies[];
};
export type BotanicalNameEntry = { kind: "BOTANICAL_NAME"; materialKey: string; botanicalName: string };
export type GlossaryTermEntry = {
  kind: "GLOSSARY_TERM";
  term: string;
  meaning: string;
  language: string | null;
  script: string | null;
};
export type ConflictEntry = { kind: "CONFLICT"; about: string; claimIds: string[] };
export type OpenQuestionEntry = { kind: "OPEN_QUESTION"; question: string; settledBy: string | null };
export type GiRecordEntry = {
  kind: "GI_RECORD";
  applicationNumber: string | null;
  certificateNumber: string | null;
  filedOn: string | null;
  registeredOn: string | null;
  journalIssue: string | null;
  proprietors: string[];
  authorisedUserCount: number | null;
};
export type AlternativeEntry = { kind: "ALTERNATIVE"; materialKey: string; alternativeKey: string };
export type StructureEntry =
  | StageAfterEntry
  | StageWhyEntry
  | NativeNameEntry
  | ReactionEntry
  | BotanicalNameEntry
  | GlossaryTermEntry
  | ConflictEntry
  | OpenQuestionEntry
  | GiRecordEntry
  | AlternativeEntry;

const tag = <K extends StructureKind>(kind: K) => oneOf([kind] as const);
const species: Shape<StructureSpecies> = object<StructureSpecies>({ name: text, formula: nullable(text) });
const maybe = nullable(text);

export const structureCheckShape: Shape<StructureCheck> = object<StructureCheck>({
  check: text,
  passed: boolean,
  reasons: list(text)
});

export const structureEntryShape: Shape<StructureEntry> = tagged<StructureEntry>("kind", {
  STAGE_AFTER: object<StageAfterEntry>({ kind: tag("STAGE_AFTER"), stageKey: text, text, colours: list(text) }),
  STAGE_WHY: object<StageWhyEntry>({ kind: tag("STAGE_WHY"), stageKey: text }),
  NATIVE_NAME: object<NativeNameEntry>({ kind: tag("NATIVE_NAME"), text, language: text, script: maybe }),
  REACTION: object<ReactionEntry>({
    kind: tag("REACTION"),
    reactionKind: text,
    stageKey: maybe,
    reactants: list(species, 1),
    products: list(species, 1)
  }),
  BOTANICAL_NAME: object<BotanicalNameEntry>({ kind: tag("BOTANICAL_NAME"), materialKey: text, botanicalName: text }),
  GLOSSARY_TERM: object<GlossaryTermEntry>({
    kind: tag("GLOSSARY_TERM"),
    term: text,
    meaning: text,
    language: maybe,
    script: maybe
  }),
  CONFLICT: object<ConflictEntry>({ kind: tag("CONFLICT"), about: text, claimIds: list(text, 2) }),
  OPEN_QUESTION: object<OpenQuestionEntry>({ kind: tag("OPEN_QUESTION"), question: text, settledBy: maybe }),
  GI_RECORD: object<GiRecordEntry>({
    kind: tag("GI_RECORD"),
    applicationNumber: maybe,
    certificateNumber: maybe,
    filedOn: maybe,
    registeredOn: maybe,
    journalIssue: maybe,
    proprietors: list(text),
    authorisedUserCount: nullable(integer)
  }),
  ALTERNATIVE: object<AlternativeEntry>({ kind: tag("ALTERNATIVE"), materialKey: text, alternativeKey: text })
});

function kindOf(value: unknown): unknown {
  return typeof value === "object" && value !== null ? (value as { kind?: unknown }).kind : undefined;
}

export function isKnownStructure(value: unknown): boolean {
  if (typeof value !== "object" || value === null) return true;
  const kinds: readonly unknown[] = STRUCTURE_KINDS;
  const item = (value as { item?: unknown }).item;
  return kinds.includes(kindOf(value)) && (typeof item !== "object" || item === null || kinds.includes(kindOf(item)));
}
