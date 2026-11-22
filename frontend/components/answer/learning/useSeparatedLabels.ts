"use client";

import { useEffect, useRef, useState, type RefObject } from "react";

import { separatedLabels, type GraphPoint, type LabelBox } from "@/lib/conceptGraph";

type Placed = { key: string; points: GraphPoint[] };

function percent(value: number, whole: number): number {
  return Math.round((value / whole) * 10000) / 100;
}

function measured(frame: HTMLElement, labels: readonly (HTMLElement | null)[], points: readonly GraphPoint[]): GraphPoint[] | null {
  const { width, height } = frame.getBoundingClientRect();
  if (width === 0 || height === 0) return null;
  const boxes: LabelBox[] = points.map((point, index) => {
    const label = labels[index]?.getBoundingClientRect();
    return { x: (point.x / 100) * width, y: (point.y / 100) * height, width: label?.width ?? 0, height: label?.height ?? 0, fixed: index === 0 };
  });
  return separatedLabels(boxes, { width, height }).map((point) => ({ x: percent(point.x, width), y: percent(point.y, height) }));
}

export function useSeparatedLabels(frame: RefObject<HTMLElement | null>, points: readonly GraphPoint[]) {
  const labels = useRef<(HTMLElement | null)[]>([]);
  const key = points.map((point) => `${point.x},${point.y}`).join(";");
  const [placed, setPlaced] = useState<Placed | null>(null);

  useEffect(() => {
    const node = frame.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      const moved = measured(node, labels.current, points);
      if (moved) setPlaced({ key, points: moved });
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [frame, key, points]);

  const shown = placed && placed.key === key ? placed.points : points;
  const label = (index: number) => (node: HTMLElement | null) => {
    labels.current[index] = node;
  };
  return { shown, label };
}
