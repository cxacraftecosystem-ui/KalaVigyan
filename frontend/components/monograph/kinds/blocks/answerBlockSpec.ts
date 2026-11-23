import { sourceRefShape } from "@/lib/answerShapes";
import { BLOCK_SHAPES, BUILT_BLOCK_KINDS, BUILT_FIGURE_KINDS, type BlockByKind, type TypedBlockKind } from "@/lib/explainerContract";
import type { MonographSources } from "@/lib/monographRender";
import { integer, list, matching, nullable, object, oneOf, parseShape, ShapeError, tagged, text, type Shape } from "@/lib/shape";
import type { SourceRef } from "@/lib/types";

export const ANSWER_BLOCK_KIND = "answer_block";
export const NOT_ON_THE_PAGE = ["quiz", "compare", "map_layer"] as const;
export const PAGE_BLOCK_KINDS = [...BUILT_BLOCK_KINDS.filter((kind) => !(NOT_ON_THE_PAGE as readonly string[]).includes(kind)), ...BUILT_FIGURE_KINDS, "artisan_voice"] as const;
export const BLOCK_FIGURE_KINDS = ["FIGURE", "TABLE"] as const;
export const SELF_TITLED_KINDS = ["region_story", "seasons"] as const;
export const WIDE_KINDS = ["region_story", "timeline_map", "zoom_story", "supply_map", "climate_risk", "seasons", "concept_graph"] as const;

export type PageBlockKind = (typeof PAGE_BLOCK_KINDS)[number] & TypedBlockKind;
export type PageBlock = BlockByKind[PageBlockKind];
export type BlockFigure = { kind: (typeof BLOCK_FIGURE_KINDS)[number]; number: number; title: string };
export type BlockSource = { key: string; ref: SourceRef };
export type AnswerBlockSpec = { block: PageBlock; figure: BlockFigure | null; sources: BlockSource[] };
export type BlockFrame = "signature" | "titled" | "numbered" | "bare";
export type BlockColumn = "main" | "wide";

export const pageBlockShape: Shape<PageBlock> = tagged<PageBlock>(
  "kind",
  Object.fromEntries(PAGE_BLOCK_KINDS.map((kind) => [kind, BLOCK_SHAPES[kind as PageBlockKind]])) as Record<string, Shape<PageBlock>>
);

export const answerBlockSpecShape: Shape<AnswerBlockSpec> = object<AnswerBlockSpec>({
  block: pageBlockShape,
  figure: nullable(object<BlockFigure>({ kind: oneOf(BLOCK_FIGURE_KINDS), number: integer, title: text })),
  sources: list(object<BlockSource>({ key: matching(/^g[1-9][0-9]*$/, "a source key"), ref: sourceRefShape }))
});

export function parseAnswerBlockSpec(spec: unknown): AnswerBlockSpec | null {
  try {
    return parseShape(answerBlockSpecShape, spec);
  } catch (error) {
    if (error instanceof ShapeError) return null;
    throw error;
  }
}

export function blockFrame(spec: AnswerBlockSpec): BlockFrame {
  if ((BUILT_FIGURE_KINDS as readonly string[]).includes(spec.block.kind)) return "signature";
  if (!spec.figure) return "bare";
  return (SELF_TITLED_KINDS as readonly string[]).includes(spec.block.kind) ? "numbered" : "titled";
}

export function blockColumn(spec: AnswerBlockSpec): BlockColumn {
  return (WIDE_KINDS as readonly string[]).includes(spec.block.kind) ? "wide" : "main";
}

export function sourceNumbers(spec: AnswerBlockSpec, sources: MonographSources): Map<string, number> {
  const numbers = new Map<string, number>();
  for (const listed of spec.sources) {
    const source = Object.hasOwn(sources, listed.key) ? sources[listed.key] : null;
    if (source) numbers.set(listed.ref.id, source.number);
  }
  return numbers;
}
