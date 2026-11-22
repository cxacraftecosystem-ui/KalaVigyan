import type { DrawnElement } from "./figureBrowser";

export type FigureDifference = { at: number; tag: string; svg: boolean; inner: boolean; property: string; approved: string; rendered: string };
export type OffsetDifference = { id: string; approved: string; rendered: string };
export type DifferenceTally = Record<string, { count: number; first: FigureDifference }>;

export const MAP_SIZED = new Set(["r", "cx", "cy", "x", "y", "d", "rx", "ry", "width", "height", "transform", "transform-origin", "perspective-origin", "inline-size", "block-size", "font-size", "line-height", "stroke-width", "--k"]);
export const BOX = "box";

const ID_REFERENCE = /url\("?#[^")]*"?\)/g;

export function withoutIdReferences(value: string | undefined): string {
  return (value ?? "").replace(ID_REFERENCE, "url(#)");
}

function elementDifferences(at: number, approved: DrawnElement, rendered: DrawnElement): FigureDifference[] {
  const base = { at, tag: rendered.tag, svg: rendered.svg, inner: rendered.inner };
  if (approved.tag !== rendered.tag) return [{ ...base, property: "tag", approved: approved.tag, rendered: rendered.tag }];
  const names = [...new Set([...Object.keys(approved.props), ...Object.keys(rendered.props)])];
  const differing = names.filter((name) => withoutIdReferences(approved.props[name]) !== withoutIdReferences(rendered.props[name]));
  const props = differing.map((name) => ({ ...base, property: name, approved: approved.props[name] ?? "", rendered: rendered.props[name] ?? "" }));
  return approved.box === rendered.box ? props : [...props, { ...base, property: BOX, approved: approved.box, rendered: rendered.box }];
}

export function figureDifferences(approved: readonly DrawnElement[], rendered: readonly DrawnElement[]): FigureDifference[] {
  if (!rendered.length) return [{ at: -1, tag: "", svg: false, inner: false, property: "figure", approved: String(approved.length), rendered: "0" }];
  const counted = approved.length === rendered.length ? [] : [{ at: -1, tag: "", svg: false, inner: false, property: "elements", approved: String(approved.length), rendered: String(rendered.length) }];
  const shared = Math.min(approved.length, rendered.length);
  return [...counted, ...Array.from({ length: shared }, (_, at) => elementDifferences(at, approved[at], rendered[at])).flat()];
}

export function sizedByTheMap(difference: FigureDifference): boolean {
  if (!difference.svg) return false;
  return difference.property === BOX ? difference.inner : MAP_SIZED.has(difference.property);
}

export function heldDifferences(differences: readonly FigureDifference[], atCaptureWidth: boolean): FigureDifference[] {
  return atCaptureWidth ? [...differences] : differences.filter((difference) => !sizedByTheMap(difference));
}

export function tally(differences: readonly FigureDifference[]): DifferenceTally {
  const found: DifferenceTally = {};
  for (const difference of differences) {
    const held = found[difference.property];
    if (held) held.count++;
    else found[difference.property] = { count: 1, first: difference };
  }
  return found;
}

export function offsetDifferences(approved: Readonly<Record<string, string>>, rendered: Readonly<Record<string, string>>): OffsetDifference[] {
  return Object.keys(approved)
    .filter((id) => Object.hasOwn(rendered, id) && rendered[id] !== approved[id])
    .map((id) => ({ id, approved: approved[id], rendered: rendered[id] }));
}
