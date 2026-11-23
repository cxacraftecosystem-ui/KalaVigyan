import { craftLinkShape, UUID, type CraftLink } from "@/lib/answerShapes";
import {
  DISCIPLINES,
  envelope,
  explainerSentenceShape,
  TERM_KEY,
  type BlockEnvelope,
  type Discipline,
  type ExplainerSentence
} from "@/lib/explainerBlockBase";
import { integer, list, nullable, object, oneOf, optional, positive, text, type Shape } from "@/lib/shape";

export const QUIZ_BLANK = "_____";

export type QuizOption = { termKey: string; text: string; sentence: ExplainerSentence };
export type QuizQuestion = { prompt: string; options: QuizOption[]; answer: number };
export type QuizBlock = BlockEnvelope<"quiz"> & { questions: QuizQuestion[] };
export type CompareTerm = { key: string; label: string };
export type CompareCell = { sentence: ExplainerSentence; pieceId: string | null };
export type CompareRow = { facet: Discipline; term: CompareTerm | null; cells: (CompareCell | null)[] };
export type CompareBlock = BlockEnvelope<"compare"> & { crafts: CraftLink[]; rows: CompareRow[] };
export type ConceptCraft = { craft: CraftLink; conceptIds: string[]; sentence: ExplainerSentence };
export type ConceptNode = { termKey: string; label: string; crafts: ConceptCraft[]; craftCount?: number };
export type ConceptGraphBlock = BlockEnvelope<"concept_graph"> & { focus: CraftLink | null; nodes: ConceptNode[] };

const quizOptionShape: Shape<QuizOption> = object<QuizOption>({ termKey: TERM_KEY, text, sentence: explainerSentenceShape });

export const quizBlockShape: Shape<QuizBlock> = object<QuizBlock>({
  ...envelope("quiz"),
  questions: list(object<QuizQuestion>({ prompt: text, options: list(quizOptionShape, 2), answer: integer }), 1)
});

export const compareBlockShape: Shape<CompareBlock> = object<CompareBlock>({
  ...envelope("compare"),
  crafts: list(craftLinkShape, 2),
  rows: list(
    object<CompareRow>({
      facet: oneOf(DISCIPLINES),
      term: nullable(object<CompareTerm>({ key: TERM_KEY, label: text })),
      cells: list(nullable(object<CompareCell>({ sentence: explainerSentenceShape, pieceId: nullable(UUID) })), 2)
    }),
    1
  )
});

export const conceptCraftShape: Shape<ConceptCraft> = object<ConceptCraft>({ craft: craftLinkShape, conceptIds: list(UUID, 1), sentence: explainerSentenceShape });

export const conceptNodeShape: Shape<ConceptNode> = object<ConceptNode>({
  termKey: TERM_KEY,
  label: text,
  crafts: list(conceptCraftShape, 2),
  craftCount: optional(positive)
});

export const conceptGraphBlockShape: Shape<ConceptGraphBlock> = object<ConceptGraphBlock>({
  ...envelope("concept_graph"),
  focus: nullable(craftLinkShape),
  nodes: list(conceptNodeShape, 1)
});

export function quizPrompt(text: string, key: string): string | null {
  const start = text.indexOf(key);
  return start < 0 ? null : `${text.slice(0, start)}${QUIZ_BLANK}${text.slice(start + key.length)}`;
}
