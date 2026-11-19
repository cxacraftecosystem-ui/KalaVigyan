"use client";

import { CitedText } from "@/components/answer/ProseBlockView";
import { STEP_NUMBER } from "@/components/answer/place/figureMarks";
import type { StageFocus } from "@/components/answer/place/RiverStage";
import type { RegionStoryBlock } from "@/lib/explainerPlace";
import { districtLine } from "@/lib/regionStory";
import { cn } from "@/lib/utils";

function StepNumber({ number, reached, on }: { number: number; reached: boolean; on: boolean }) {
  const tone = on ? "bg-indigo text-indigo-on" : reached ? "bg-ink-1 text-ground" : "border border-dashed border-rule-strong text-ink-3";
  return (
    <span aria-hidden className={cn(STEP_NUMBER, tone)}>
      {number}
    </span>
  );
}

export function StorySteps({ block, focus, step }: { block: RegionStoryBlock; focus: StageFocus; step: number | null }) {
  return (
    <ol className="grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-ink-1" aria-label="Story" data-testid="story-steps">
      {block.steps.map((entry, index) => {
        const place = districtLine(block, entry.districtLgd);
        const on = step === index;
        const reached = focus.reached[index] ?? true;
        const header = (
          <>
            <StepNumber number={index + 1} reached={reached} on={on && place !== null} />
            <span className="kicker min-w-0">{place ?? `Step ${index + 1}`}</span>
          </>
        );
        return (
          <li
            key={entry.sentence.id}
            aria-current={on ? "step" : undefined}
            data-reached={reached ? "true" : "false"}
            data-testid="story-step"
            className={cn("min-w-0 border-b border-s-2 border-b-rule py-3 ps-3 transition-colors duration-state sm:ps-4", on ? "border-s-ink-1" : "border-s-transparent")}
          >
            {place ? (
              <button type="button" aria-pressed={on} onClick={() => focus.onStep(index)} className="flex min-h-target w-full items-center gap-3 rounded-control text-start hover:text-indigo-hover">
                {header}
              </button>
            ) : (
              <div className="flex min-h-target items-center gap-3">{header}</div>
            )}
            <CitedText id={entry.sentence.id} sentences={[entry.sentence]} className="mt-1 max-w-measure ps-11 font-reading text-body-sm text-ink-1" />
          </li>
        );
      })}
    </ol>
  );
}
