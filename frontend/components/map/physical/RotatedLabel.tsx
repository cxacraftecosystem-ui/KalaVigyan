import type { ReactNode } from "react";

import { HALO_WIDTH, LABEL_SIZE } from "@/components/map/MapCanvas";
import { cn } from "@/lib/utils";

export const TIER_HIDDEN: Readonly<Record<number, string>> = { 1: "", 2: "max-sm:hidden", 3: "max-lg:hidden" };

export type RotatedLabelProps = {
  x: number;
  y: number;
  angle: number;
  children: ReactNode;
  tone?: string;
  anchor?: "start" | "middle" | "end";
  dx?: number;
  lift?: boolean;
  italic?: boolean;
  weight?: "normal" | "medium";
  className?: string;
};

export function RotatedLabel({ x, y, angle, children, tone = "var(--map-label)", anchor = "middle", dx = 0, lift = false, italic = false, weight = "normal", className }: RotatedLabelProps) {
  return (
    <text
      x={x + dx}
      y={y}
      dy={lift ? "-0.55em" : undefined}
      transform={angle ? `rotate(${angle} ${x} ${y})` : undefined}
      textAnchor={anchor}
      dominantBaseline="central"
      fill={tone}
      stroke="var(--map-label-halo)"
      strokeLinejoin="round"
      paintOrder="stroke"
      className={cn("pointer-events-none", italic ? "font-reading italic" : "font-ui", weight === "medium" ? "font-medium" : "font-normal", className)}
      style={{ fontSize: LABEL_SIZE, strokeWidth: HALO_WIDTH }}
    >
      {children}
    </text>
  );
}
