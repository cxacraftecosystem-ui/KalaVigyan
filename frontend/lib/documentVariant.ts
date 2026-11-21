import { RIGHT_TO_LEFT, type DocumentLanguageCode } from "@/lib/documentLanguages";
import { ENGLISH, type MonographDocument, type MonographMark, type MonographNode, type MonographUnit } from "@/lib/monographDocument";

export const FIXED_MARKS = ["i", "sub", "sup"] as const;
export const NAME_UNITS = ["masthead-title"] as const;
const LETTER = /\p{L}/u;

export type PassageLeaf = { text: string; fixed: boolean; cited: boolean };
export type DraftPassage = { key: string; english: readonly string[]; texts: readonly string[] };

export function passageLeaves(nodes: readonly MonographNode[], fixed = false, cited = false): PassageLeaf[] {
  return nodes.flatMap((node) => {
    if (typeof node === "string") return [{ text: node, fixed, cited }];
    const mark = node.m;
    return passageLeaves(node.c ?? [], fixed || (FIXED_MARKS as readonly string[]).includes(mark), cited || mark === "cite");
  });
}

export function isTranslatable(key: string, nodes: readonly MonographNode[]): boolean {
  if ((NAME_UNITS as readonly string[]).includes(key)) return false;
  return passageLeaves(nodes).some((leaf) => !leaf.fixed && LETTER.test(leaf.text));
}

export function withTexts(nodes: readonly MonographNode[], texts: readonly string[]): MonographNode[] {
  let at = 0;
  const replace = (given: readonly MonographNode[]): MonographNode[] =>
    given.map((node) => {
      if (typeof node === "string") return texts[at++] ?? "";
      return node.c ? ({ ...node, c: replace(node.c) } as MonographMark) : node;
    });
  const replaced = replace(nodes);
  if (at !== texts.length) throw new Error("A translation gives one text for each English text");
  return replaced;
}

function sameLeaves(unit: MonographUnit, english: readonly string[]): boolean {
  const leaves = passageLeaves(unit.nodes).map((leaf) => leaf.text);
  return leaves.length === english.length && leaves.every((text, at) => text === english[at]);
}

export function draftVariant(document: MonographDocument, language: DocumentLanguageCode, script: string, passages: readonly DraftPassage[]): MonographDocument {
  const drafts = new Map(passages.map((passage) => [passage.key, passage]));
  let total = 0;
  let translated = 0;
  const units: Record<string, MonographUnit> = {};
  for (const [key, unit] of Object.entries(document.content.units)) {
    if (!isTranslatable(key, unit.nodes)) {
      units[key] = unit;
      continue;
    }
    total += 1;
    const draft = drafts.get(key);
    const current = draft !== undefined && sameLeaves(unit, draft.english);
    translated += current ? 1 : 0;
    units[key] = current ? { ...unit, nodes: withTexts(unit.nodes, draft.texts), lang: language } : { ...unit, lang: ENGLISH };
  }
  const direction = (RIGHT_TO_LEFT as readonly string[]).includes(language) ? "rtl" : "ltr";
  const translation = { sourceLanguage: ENGLISH, sourceVersion: document.version, script, direction, passages: total, translated, held: 0 } as const;
  return { ...document, language, content: { ...document.content, units }, translation };
}
