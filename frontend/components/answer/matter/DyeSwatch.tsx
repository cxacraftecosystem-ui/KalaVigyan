import { cn } from "@/lib/utils";

export const SWATCH_FRAME = "block rounded-plate border border-ink-2 bg-raised p-0.5 [forced-color-adjust:none]";

export function WeavePattern({ id }: { id: string }) {
  return (
    <defs>
      <pattern id={id} width="3" height="3" patternUnits="userSpaceOnUse">
        <path d="M0 3 L3 0" stroke="var(--dye-kut)" strokeOpacity="0.07" strokeWidth="0.6" />
        <path d="M0 0 L3 3" stroke="var(--dye-cloth)" strokeOpacity="0.06" strokeWidth="0.5" />
      </pattern>
    </defs>
  );
}

export function DyeSwatch({ fill, weave, className }: { fill: string; weave: string; className?: string }) {
  return (
    <span aria-hidden className={cn(SWATCH_FRAME, "h-7 w-7 shrink-0", className)}>
      <svg viewBox="0 0 24 24" className="block h-full w-full" focusable="false">
        <rect width="24" height="24" fill={fill} />
        <rect width="24" height="24" fill={`url(#${weave})`} />
      </svg>
    </span>
  );
}

export function WovenLayer({ fill, weave }: { fill: string; weave: string }) {
  return (
    <svg viewBox="0 0 120 24" preserveAspectRatio="none" className="absolute inset-0 block h-full w-full" focusable="false">
      <rect width="120" height="24" fill={fill} />
      <rect width="120" height="24" fill={`url(#${weave})`} />
    </svg>
  );
}
