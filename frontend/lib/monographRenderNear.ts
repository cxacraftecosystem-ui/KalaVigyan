import type { MonographDocument } from "@/lib/monographDocument";
import { citedSourceKeys, nodesText } from "@/lib/monographRender";
import { componentUnits, type ChapterBlock, type ChapterPlan, type PagePlan, type Passage, type PassagePiece } from "@/lib/monographRenderLayout";

export const LAYOUT_DATA = "page-layout";
const WORD = /[\p{L}][\p{L}-]{3,}/gu;
const SOURCE_WEIGHT = 2;
const SHARED_FLOOR = 0.5;
const COMMON = new Set([
  "about", "after", "also", "among", "another", "because", "been", "before", "being", "between", "both", "but", "called", "cloth", "could", "craft", "crafts", "does", "each", "either",
  "from", "have", "here", "into", "itself", "made", "make", "many", "more", "most", "much", "only", "other", "over", "same", "some", "such", "than", "that", "their", "them", "then",
  "there", "these", "they", "this", "those", "through", "under", "until", "used", "uses", "using", "very", "were", "what", "when", "where", "which", "while", "with", "within", "would", "your"
]);

export type Figure = { label: string; words: ReadonlySet<string>; sources: ReadonlySet<string> };
export type Paragraph = { block: number; piece: number; words: ReadonlySet<string>; sources: ReadonlySet<string> };

export function words(text: string): Set<string> {
  return new Set([...text.toLowerCase().matchAll(WORD)].map((found) => found[0].replace(/-+$/, "")).filter((word) => !COMMON.has(word)));
}

export function arrangedLabels(document: MonographDocument): Set<string> {
  const layout = document.content.data[LAYOUT_DATA];
  const entries = layout && typeof layout === "object" ? (layout as { entries?: unknown }).entries : null;
  if (!Array.isArray(entries)) return new Set();
  return new Set(entries.flatMap((entry) => (entry && typeof entry === "object" && typeof (entry as { ref?: unknown }).ref === "string" ? [(entry as { ref: string }).ref] : [])));
}

function figure(document: MonographDocument, label: string): Figure {
  const component = document.content.components.find((found) => found.label === label);
  const units = componentUnits(document, label).map((ref) => document.content.units[ref]).filter(Boolean);
  const text = [component?.title ?? "", component?.description ?? "", ...units.map((unit) => nodesText(unit.nodes))].join(" ");
  return { label, words: words(text), sources: new Set(units.flatMap((unit) => citedSourceKeys(unit.nodes))) };
}

function paragraphs(document: MonographDocument, blocks: readonly ChapterBlock[]): Paragraph[] {
  const units = document.content.units;
  return blocks.flatMap((block, at) =>
    block.kind !== "passage"
      ? []
      : block.pieces.flatMap((piece, index) => {
          if (piece.kind !== "paragraph") return [];
          const nodes = piece.refs.flatMap((ref) => units[ref]?.nodes ?? []);
          return [{ block: at, piece: index, words: words(nodesText(nodes)), sources: new Set(citedSourceKeys(nodes)) }];
        })
  );
}

export function rarity(found: readonly Paragraph[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const paragraph of found) for (const word of paragraph.words) counts.set(word, (counts.get(word) ?? 0) + 1);
  return new Map([...counts].map(([word, count]) => [word, Math.log((found.length + 1) / count)]));
}

export function nearness(item: Figure, paragraph: Paragraph, weights: ReadonlyMap<string, number>): number {
  let score = 0;
  for (const word of item.words) if (paragraph.words.has(word)) score += weights.get(word) ?? 0;
  for (const source of item.sources) if (paragraph.sources.has(source)) score += SOURCE_WEIGHT;
  return score;
}

export function anchors(items: readonly Figure[], found: readonly Paragraph[]): Map<string, Paragraph> {
  const weights = rarity(found);
  const taken = new Set<Paragraph>();
  const chosen = new Map<string, Paragraph>();
  for (const item of items) {
    const ranked = found.map((paragraph) => ({ paragraph, score: nearness(item, paragraph, weights) })).filter((entry) => entry.score > 0).sort((a, b) => b.score - a.score);
    if (!ranked.length) continue;
    const free = ranked.find((entry) => !taken.has(entry.paragraph) && entry.score >= ranked[0].score * SHARED_FLOOR);
    const pick = (free ?? ranked[0]).paragraph;
    taken.add(pick);
    chosen.set(item.label, pick);
  }
  return chosen;
}

function trailing(blocks: readonly ChapterBlock[]): string[] {
  const out: string[] = [];
  for (let at = blocks.length - 1; at >= 0; at -= 1) {
    const block = blocks[at];
    if (block.kind !== "component") break;
    out.unshift(block.label);
  }
  return out;
}

export function interleaved(block: Passage, anchored: ReadonlyMap<number, readonly string[]>): ChapterBlock[] {
  const out: ChapterBlock[] = [];
  let pieces: PassagePiece[] = [];
  const flush = () => {
    if (!pieces.length) return;
    out.push(out.some((found) => found.kind === "passage") ? { kind: "passage", head: false, pieces, notes: [] } : { ...block, pieces });
    pieces = [];
  };
  block.pieces.forEach((piece, index) => {
    pieces.push(piece);
    const labels = anchored.get(index);
    if (!labels) return;
    flush();
    labels.forEach((label) => out.push({ kind: "component", label }));
  });
  flush();
  return out;
}

function rebuilt(blocks: readonly ChapterBlock[], chosen: ReadonlyMap<string, Paragraph>): ChapterBlock[] {
  const byBlock = new Map<number, Map<number, string[]>>();
  for (const [label, paragraph] of chosen) {
    const pieces = byBlock.get(paragraph.block) ?? new Map<number, string[]>();
    pieces.set(paragraph.piece, [...(pieces.get(paragraph.piece) ?? []), label]);
    byBlock.set(paragraph.block, pieces);
  }
  return blocks.flatMap((block, at) => {
    if (block.kind === "component" && chosen.has(block.label)) return [];
    if (block.kind !== "passage") return [block];
    const anchored = byBlock.get(at);
    return anchored ? interleaved(block, anchored) : [block];
  });
}

export function figuresNearText(document: MonographDocument, chapter: ChapterPlan): ChapterPlan {
  const arranged = arrangedLabels(document);
  const moved = trailing(chapter.blocks).filter((label) => !arranged.has(label));
  const found = paragraphs(document, chapter.blocks);
  if (!moved.length || !found.length) return chapter;
  const chosen = anchors(moved.map((label) => figure(document, label)), found);
  if (!chosen.size) return chapter;
  return { ...chapter, blocks: rebuilt(chapter.blocks, chosen) };
}

export function placedPlan(document: MonographDocument, plan: PagePlan): PagePlan {
  if (document.shell !== null) return plan;
  return { ...plan, chapters: plan.chapters.map((chapter) => figuresNearText(document, chapter)) };
}
