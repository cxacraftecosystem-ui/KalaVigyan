import type { CraftLink } from "@/lib/answerShapes";
import type { ConceptCraft, ConceptNode } from "@/lib/explainerLearning";
import { listText } from "@/lib/format";

export const GRAPH_CRAFTS_MAX = 8;
export const LIST_CRAFTS_START = 6;

export type GraphPoint = { x: number; y: number };
export type GraphCraft = { entry: ConceptCraft; at: GraphPoint; focus: boolean };
export type ConceptGraphLayout = { crafts: GraphCraft[]; more: { count: number; at: GraphPoint } | null };

export const GRAPH_CENTRE: GraphPoint = { x: 50, y: 50 };
const RADIUS_X = 34;
const RADIUS_Y = 36;

export function ringPoints(count: number): GraphPoint[] {
  return Array.from({ length: count }, (_, index) => {
    const angle = -Math.PI / 2 + (index * 2 * Math.PI) / count;
    return { x: round(GRAPH_CENTRE.x + RADIUS_X * Math.cos(angle)), y: round(GRAPH_CENTRE.y + RADIUS_Y * Math.sin(angle)) };
  });
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}

export function graphLayout(node: ConceptNode, focus: CraftLink | null): ConceptGraphLayout {
  const overflow = node.crafts.length > GRAPH_CRAFTS_MAX;
  const drawn = overflow ? node.crafts.slice(0, GRAPH_CRAFTS_MAX - 1) : node.crafts;
  const points = ringPoints(drawn.length + (overflow ? 1 : 0));
  return {
    crafts: drawn.map((entry, index) => ({ entry, at: points[index], focus: entry.craft.slug === focus?.slug })),
    more: overflow ? { count: node.crafts.length - drawn.length, at: points[drawn.length] } : null
  };
}

export function graphSummary(node: ConceptNode): string {
  return `${node.label} is shared by ${listText(node.crafts.map((entry) => entry.craft.name))}`;
}

export function nodeChoiceLabel(node: ConceptNode): string {
  return `${node.label} · ${node.crafts.length}`;
}

export function shownCrafts(node: ConceptNode, all: boolean): ConceptCraft[] {
  return all ? node.crafts : node.crafts.slice(0, LIST_CRAFTS_START);
}

export function chosenNode(nodes: readonly ConceptNode[], termKey: string | null): ConceptNode {
  return nodes.find((node) => node.termKey === termKey) ?? nodes[0];
}

export type LabelBox = { x: number; y: number; width: number; height: number; fixed?: boolean };
export type Frame = { width: number; height: number };

export const LABEL_GAP_PX = 6;
const SEPARATION_PASSES = 24;

function overlap(a: LabelBox, b: LabelBox, gap: number): number {
  const across = Math.abs(a.x - b.x) < (a.width + b.width) / 2 + gap;
  const needed = (a.height + b.height) / 2 + gap - Math.abs(a.y - b.y);
  return across && needed > 0 ? needed : 0;
}

function within(box: LabelBox, frame: Frame): LabelBox {
  const half = Math.min(box.height / 2, frame.height / 2);
  return { ...box, y: Math.min(Math.max(box.y, half), frame.height - half) };
}

function room(box: LabelBox, space: number): number {
  return box.fixed ? 0 : Math.max(0, space);
}

function pushApart(boxes: LabelBox[], pair: [number, number], needed: number, frame: Frame): boolean {
  const [upper, lower] = boxes[pair[0]].y <= boxes[pair[1]].y ? pair : [pair[1], pair[0]];
  const up = room(boxes[upper], boxes[upper].y - boxes[upper].height / 2);
  const down = room(boxes[lower], frame.height - boxes[lower].height / 2 - boxes[lower].y);
  if (up + down === 0) return false;
  const fall = Math.min(down, needed - Math.min(up, needed / 2));
  const rise = Math.min(up, needed - fall);
  boxes[upper] = { ...boxes[upper], y: boxes[upper].y - rise };
  boxes[lower] = { ...boxes[lower], y: boxes[lower].y + fall };
  return rise + fall > 0;
}

function separationPass(boxes: LabelBox[], frame: Frame, gap: number): boolean {
  let moved = false;
  for (let i = 0; i < boxes.length; i += 1) {
    for (let j = i + 1; j < boxes.length; j += 1) {
      const needed = overlap(boxes[i], boxes[j], gap);
      if (needed > 0 && pushApart(boxes, [i, j], needed, frame)) moved = true;
    }
  }
  return moved;
}

export function separatedLabels(boxes: readonly LabelBox[], frame: Frame, gap = LABEL_GAP_PX): GraphPoint[] {
  const placed = boxes.map((box) => (box.fixed ? box : within(box, frame)));
  let pass = 0;
  while (pass < SEPARATION_PASSES && separationPass(placed, frame, gap)) pass += 1;
  return placed.map((box) => ({ x: box.x, y: box.y }));
}
