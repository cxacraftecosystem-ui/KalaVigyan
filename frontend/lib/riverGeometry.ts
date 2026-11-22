export type Point = readonly [number, number];
export type Bounds = { minX: number; minY: number; maxX: number; maxY: number };
export type View = { x: number; y: number; width: number; height: number };
export type Framing = { aspect: number; minSpan: number; padding: number };

function distance(a: Point, b: Point): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

function nearest(point: Point, line: readonly Point[]): number {
  return Math.min(distance(point, line[0]), distance(point, line[line.length - 1]));
}

function reversed(line: readonly Point[]): Point[] {
  return [...line].reverse();
}

export function orientDownstream(lines: readonly (readonly Point[])[]): Point[][] {
  const oriented: Point[][] = [];
  lines.forEach((line, index) => {
    const next = lines[index + 1];
    const previous = oriented[index - 1];
    const start = line[0];
    const end = line[line.length - 1];
    if (next) oriented.push(nearest(start, next) < nearest(end, next) ? reversed(line) : [...line]);
    else if (previous) {
      const joint = previous[previous.length - 1];
      oriented.push(distance(end, joint) < distance(start, joint) ? reversed(line) : [...line]);
    } else oriented.push([...line]);
  });
  return oriented;
}

export function joinLines(lines: readonly (readonly Point[])[]): Point[] {
  const joined: Point[] = [];
  for (const line of lines) {
    for (const point of line) {
      const last = joined[joined.length - 1];
      if (!last || last[0] !== point[0] || last[1] !== point[1]) joined.push(point);
    }
  }
  return joined;
}

export function cumulativeLengths(points: readonly Point[]): number[] {
  const lengths = [0];
  for (let index = 1; index < points.length; index += 1) lengths.push(lengths[index - 1] + distance(points[index - 1], points[index]));
  return lengths;
}

export function lineLength(points: readonly Point[]): number {
  return cumulativeLengths(points)[points.length - 1] ?? 0;
}

export function pointAlong(points: readonly Point[], lengths: readonly number[], fraction: number): Point {
  const total = lengths[lengths.length - 1];
  const target = Math.min(Math.max(fraction, 0), 1) * total;
  const after = lengths.findIndex((length) => length >= target);
  if (after <= 0) return points[0];
  const span = lengths[after] - lengths[after - 1];
  const share = span === 0 ? 0 : (target - lengths[after - 1]) / span;
  const [x0, y0] = points[after - 1];
  const [x1, y1] = points[after];
  return [x0 + (x1 - x0) * share, y0 + (y1 - y0) * share];
}

export function boundsOf(sets: Iterable<readonly Point[]>): Bounds | null {
  let bounds: Bounds | null = null;
  for (const points of sets) {
    for (const [x, y] of points) {
      bounds = bounds
        ? { minX: Math.min(bounds.minX, x), minY: Math.min(bounds.minY, y), maxX: Math.max(bounds.maxX, x), maxY: Math.max(bounds.maxY, y) }
        : { minX: x, minY: y, maxX: x, maxY: y };
    }
  }
  return bounds;
}

export function framedView(bounds: Bounds, framing: Framing): View {
  const centreX = (bounds.minX + bounds.maxX) / 2;
  const centreY = (bounds.minY + bounds.maxY) / 2;
  const padded = 1 + framing.padding * 2;
  let width = Math.max((bounds.maxX - bounds.minX) * padded, framing.minSpan);
  let height = Math.max((bounds.maxY - bounds.minY) * padded, framing.minSpan / framing.aspect);
  if (width / height < framing.aspect) width = height * framing.aspect;
  else height = width / framing.aspect;
  return { x: centreX - width / 2, y: centreY - height / 2, width, height };
}

export function withinView(point: Point, view: View, margin = 0): boolean {
  const [x, y] = point;
  return x >= view.x - margin && x <= view.x + view.width + margin && y >= view.y - margin && y <= view.y + view.height + margin;
}

export function pathData(lines: readonly (readonly Point[])[]): string {
  return lines
    .filter((line) => line.length >= 2)
    .map((line) => line.map(([x, y], index) => `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`).join(""))
    .join("");
}

export function viewPercent(point: Point, view: View): { left: string; top: string } {
  return {
    left: `${(((point[0] - view.x) / view.width) * 100).toFixed(3)}%`,
    top: `${(((point[1] - view.y) / view.height) * 100).toFixed(3)}%`
  };
}
