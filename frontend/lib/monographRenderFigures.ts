import type { MonographDocument, MonographNode, MonographUnit } from "@/lib/monographDocument";
import { nodesText } from "@/lib/monographRender";
import { componentBundles, type PagePlan } from "@/lib/monographRenderLayout";
import { UNIT_REF } from "@/lib/unitIds";

const FIGURE_KEY = /^[a-z]+:\d+$/;
const NUMBER_TEXT = /^(Fig\.|Table)\s+\d+$/;
const NUMBER_IN_TEXT = /(Fig\.|Table)\s+\d+/;
const DIGITS = /\d+/;
const ANSWER_BLOCK = "answer_block";
const TABLE_KIND = "TABLE";
const FIGURE_WORD = "Fig.";
const TABLE_WORD = "Table";

type Fields = Readonly<Record<string, unknown>>;
export type PageFigure = { key: string; word: string; unit: string | null; label: string };

function isRecord(value: unknown): value is Fields {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function numberedHeads(value: unknown): { key: string; unit: string }[] {
  if (Array.isArray(value)) return value.flatMap(numberedHeads);
  if (!isRecord(value)) return [];
  const own: { key: string; unit: string }[] = [];
  const { figure, number } = value;
  if (typeof figure === "string" && FIGURE_KEY.test(figure) && typeof number === "string" && UNIT_REF.test(number)) own.push({ key: figure, unit: number });
  if (isRecord(number) && typeof number.unit === "string" && typeof number.ref === "string") own.push({ key: number.ref, unit: number.unit });
  return [...own, ...Object.values(value).flatMap(numberedHeads)];
}

function blockFigure(label: string, kind: string, spec: Fields | null): PageFigure | null {
  const figure = kind === ANSWER_BLOCK && spec ? spec.figure : null;
  if (!isRecord(figure) || typeof figure.number !== "number") return null;
  return { key: `${label}#figure`, word: figure.kind === TABLE_KIND ? TABLE_WORD : FIGURE_WORD, unit: null, label: "" };
}

function componentFigures(document: MonographDocument, label: string): PageFigure[] {
  const found: PageFigure[] = [];
  for (const [name, bundle] of Object.entries(componentBundles(document, label))) {
    const block = blockFigure(name, bundle.component.kind, bundle.spec);
    if (block) found.push(block);
    for (const head of numberedHeads(bundle.spec)) {
      const unit = document.content.units[head.unit];
      const text = unit ? nodesText(unit.nodes).trim() : "";
      const word = NUMBER_TEXT.exec(text)?.[1];
      if (word) found.push({ key: head.key, word, unit: head.unit, label: "" });
    }
  }
  return found;
}

export function pageFigures(document: MonographDocument, plan: PagePlan): PageFigure[] {
  const seen = new Set<string>();
  const counts = new Map<string, number>();
  const out: PageFigure[] = [];
  for (const chapter of plan.chapters) {
    for (const block of chapter.blocks) {
      if (block.kind !== "component") continue;
      for (const figure of componentFigures(document, block.label)) {
        if (seen.has(figure.key)) continue;
        seen.add(figure.key);
        const count = (counts.get(figure.word) ?? 0) + 1;
        counts.set(figure.word, count);
        out.push({ ...figure, label: `${figure.word} ${count}` });
      }
    }
  }
  return out;
}

function refigured(nodes: readonly MonographNode[], labels: ReadonlyMap<string, string>): MonographNode[] {
  return nodes.map((node) => {
    if (typeof node === "string") return node;
    const label = node.m === "figref" && typeof node.ref === "string" ? labels.get(node.ref) : undefined;
    if (label) return { ...node, c: (node.c ?? []).map((child) => (typeof child === "string" ? child.replace(NUMBER_IN_TEXT, label) : child)) };
    return node.c ? { ...node, c: refigured(node.c, labels) } : node;
  });
}

export function renumbered(nodes: readonly MonographNode[], digits: string): MonographNode[] {
  let done = false;
  const walk = (list: readonly MonographNode[]): MonographNode[] =>
    list.map((node) => {
      if (done) return node;
      if (typeof node === "string") {
        if (!DIGITS.test(node)) return node;
        done = true;
        return node.replace(DIGITS, digits);
      }
      return node.c ? { ...node, c: walk(node.c) } : node;
    });
  return walk(nodes);
}

function playerFigures(document: MonographDocument): Map<string, string> {
  const found = new Map<string, string>();
  for (const spec of Object.values(document.specs)) {
    const head = spec.head;
    if (typeof spec.id === "string" && isRecord(head) && typeof head.figure === "string") found.set(spec.id, head.figure);
  }
  return found;
}

function relabelled(value: unknown, labels: ReadonlyMap<string, string>, players: ReadonlyMap<string, string>): unknown {
  if (Array.isArray(value)) return value.map((item) => relabelled(item, labels, players));
  if (!isRecord(value)) return value;
  const out: Record<string, unknown> = Object.fromEntries(Object.entries(value).map(([key, item]) => [key, relabelled(item, labels, players)]));
  if (typeof value.figureLabel !== "string") return out;
  const key = (typeof value.player === "string" ? players.get(value.player) : undefined) ?? (typeof value.figure === "string" ? value.figure : "");
  const label = labels.get(key);
  if (label) out.figureLabel = label;
  return out;
}

function blockNumbered(spec: Record<string, unknown>, label: string | undefined): Record<string, unknown> {
  if (!label || !isRecord(spec.figure)) return spec;
  return { ...spec, figure: { ...spec.figure, number: Number(label.split(" ")[1]) } };
}

export function numberedDocument(document: MonographDocument, plan: PagePlan): MonographDocument {
  if (document.shell !== null) return document;
  const figures = pageFigures(document, plan);
  if (!figures.length) return document;
  const labels = new Map(figures.map((figure) => [figure.key, figure.label]));
  const numbers = new Map(figures.flatMap((figure) => (figure.unit ? [[figure.unit, figure.label] as const] : [])));
  const players = playerFigures(document);
  const units: Record<string, MonographUnit> = Object.fromEntries(
    Object.entries(document.content.units).map(([ref, unit]) => [ref, numbers.has(ref) ? { ...unit, nodes: renumbered(unit.nodes, (numbers.get(ref) ?? "").split(" ")[1] ?? "") } : { ...unit, nodes: refigured(unit.nodes, labels) }])
  );
  const specs = Object.fromEntries(
    Object.entries(document.specs).map(([label, spec]) => [label, blockNumbered(relabelled(spec, labels, players) as Record<string, unknown>, labels.get(`${label}#figure`))])
  );
  return { ...document, specs, content: { ...document.content, units } };
}
