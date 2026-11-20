import type { GateCheck, QueueAction, StructureReview } from "@/lib/reviewQueueContract";
import { codeLabel } from "@/lib/reviewQueueView";
import type { GiRecordEntry, StructureCheck, StructureEntry, StructureKind, StructureSpecies } from "@/lib/structureReviewContract";

export type EntryLine = { term: string; value: string; lang?: string; script?: string };

export const STRUCTURE_KIND_LABELS: Record<StructureKind, string> = {
  STAGE_AFTER: "After a stage",
  STAGE_WHY: "Why a stage works",
  NATIVE_NAME: "Native name",
  REACTION: "Reaction",
  BOTANICAL_NAME: "Botanical name",
  GLOSSARY_TERM: "Glossary term",
  CONFLICT: "Facts that disagree",
  OPEN_QUESTION: "Open question",
  GI_RECORD: "GI record"
};

const GI_PARTS: [keyof GiRecordEntry, string][] = [
  ["applicationNumber", "Application number"],
  ["certificateNumber", "Certificate number"],
  ["filedOn", "Filed on"],
  ["registeredOn", "Registered on"],
  ["journalIssue", "Journal issue"],
  ["authorisedUserCount", "Authorised users"]
];

export function structureActions(review: StructureReview): QueueAction[] {
  return review.stale ? ["reject"] : ["approve", "reject"];
}

export function speciesLine(species: StructureSpecies[]): string {
  return species.map((each) => (each.formula ? `${each.name} (${each.formula})` : each.name)).join(" + ");
}

export function entryLines(entry: StructureEntry): EntryLine[] {
  switch (entry.kind) {
    case "STAGE_AFTER":
      return [{ term: "After the stage", value: entry.text }, ...listed("Colours", entry.colours.map((colour) => colour.toLowerCase()))];
    case "STAGE_WHY":
      return [{ term: "Stage", value: entry.stageKey }];
    case "NATIVE_NAME":
      return [{ term: "Name", value: entry.text, lang: entry.language, script: entry.script ?? undefined }, { term: "Language", value: entry.language }];
    case "REACTION":
      return [
        { term: "Kind", value: codeLabel(entry.reactionKind) },
        { term: "Reactants", value: speciesLine(entry.reactants) },
        { term: "Products", value: speciesLine(entry.products) }
      ];
    case "BOTANICAL_NAME":
      return [{ term: "Botanical name", value: entry.botanicalName }];
    case "GLOSSARY_TERM":
      return [{ term: "Term", value: entry.term, lang: entry.language ?? undefined, script: entry.script ?? undefined }, { term: "Meaning", value: entry.meaning }];
    case "CONFLICT":
      return [{ term: "About", value: entry.about }];
    case "OPEN_QUESTION":
      return [{ term: "Question", value: entry.question }, ...listed("Settled by", entry.settledBy ? [entry.settledBy] : [])];
    case "GI_RECORD":
      return giLines(entry);
  }
}

export function checkLines(checks: StructureCheck[]): GateCheck[] {
  return checks.map((check) => ({ gate: check.check, passed: check.passed, reasons: check.reasons, model: null, related: [] }));
}

export function writesLine(review: StructureReview): string {
  if (review.stale) return `The page has moved on, so it can only be rejected: ${review.stale}.`;
  if (review.kind === "CONFLICT") return `Approving shows these facts as disagreeing on the ${review.subjectName} page and in its dossier.`;
  return `Approving writes it into the ${review.subjectName} page and its dossier, with its fact cited.`;
}

export function targetLine(review: StructureReview): string {
  return review.target ? `${review.subjectName} · ${review.target}` : review.subjectName;
}

function listed(term: string, values: string[]): EntryLine[] {
  return values.length ? [{ term, value: values.join(", ") }] : [];
}

function giLines(entry: GiRecordEntry): EntryLine[] {
  const parts = GI_PARTS.flatMap(([key, term]) => {
    const value = entry[key];
    return value === null || Array.isArray(value) ? [] : [{ term, value: String(value) }];
  });
  return [...parts, ...listed("Proprietors", entry.proprietors)];
}
