"use client";

import { useEffect, useId } from "react";
import { ArrowRight } from "lucide-react";

import { CitationChips } from "@/components/answer/CitationContext";
import { DyeSwatch, SWATCH_FRAME, WeavePattern, WovenLayer } from "@/components/answer/matter/DyeSwatch";
import { motionClass, useNamedMotion } from "@/components/motion/useNamedMotion";
import type { ReactionStep, StepColour } from "@/lib/explainerMatter";
import { changeMotion, COLOUR_LABEL, colourChange, colourChangeLine, DYE_FILL, type ColourChange } from "@/lib/reactionPlayer";
import { cn } from "@/lib/utils";

function Swatch({ colour, label, weave }: { colour: StepColour; label: string; weave: string }) {
  return (
    <span className="inline-flex min-w-0 items-center gap-2" data-testid="step-colour" data-side={colour.side} data-colour={colour.colour}>
      <DyeSwatch fill={DYE_FILL[colour.colour]} weave={weave} />
      <span className="font-ui text-label text-ink-2">
        <span className="font-semibold text-ink-1">{label}</span> {COLOUR_LABEL[colour.colour].toLowerCase()}
      </span>
    </span>
  );
}

function Cloth({ change, animate, weave }: { change: ColourChange; animate: boolean; weave: string }) {
  const motion = changeMotion(change);
  const [layer, play] = useNamedMotion<HTMLSpanElement>();
  useEffect(() => {
    if (animate) play();
  }, [animate, play]);
  const start = change.before ?? change.after;
  const end = change.after ?? change.before;
  if (!start || !end) return null;
  const [base, over] = motion === "oxidise" ? [end, start] : [start, end];
  return (
    <span aria-hidden className={cn(SWATCH_FRAME, "h-12 w-full")} data-testid="step-cloth" data-motion={motion}>
      <span className="relative block h-full w-full overflow-hidden">
        <WovenLayer fill={DYE_FILL[base.colour]} weave={weave} />
        <span ref={layer} className={cn("absolute inset-0 block", motionClass(motion))}>
          <WovenLayer fill={DYE_FILL[over.colour]} weave={weave} />
        </span>
      </span>
    </span>
  );
}

function stated(change: ColourChange): StepColour[] {
  const colours = [change.before, change.after].filter((colour): colour is StepColour => colour !== null);
  return colours.filter((colour, index) => colours.findIndex((other) => other.stated === colour.stated) === index);
}

export function StepColours({ step, animate }: { step: Pick<ReactionStep, "colours">; animate: boolean }) {
  const weave = `kv-step-weave${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const change = colourChange(step);
  if (!change) return null;
  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-2" data-testid="step-colours">
      <svg width={0} height={0} aria-hidden className="absolute">
        <WeavePattern id={weave} />
      </svg>
      <p className="kicker">{colourChangeLine(change)}</p>
      <Cloth change={change} animate={animate} weave={weave} />
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        {change.before ? <Swatch colour={change.before} label="Before" weave={weave} /> : null}
        {change.before && change.after ? <ArrowRight className="h-4 w-4 shrink-0 text-ink-3 rtl:-scale-x-100" aria-hidden /> : null}
        {change.after ? <Swatch colour={change.after} label="After" weave={weave} /> : null}
      </p>
      {stated(change).map((colour) => (
        <p key={colour.side} className="font-reading text-quote italic text-ink-2">
          <q>{colour.stated}</q>
          <CitationChips citations={colour.citations} />
        </p>
      ))}
    </div>
  );
}
