"use client";

import { CraftChoice } from "@/components/ask/CraftChoice";
import { LanguagePicker } from "@/components/LanguagePicker";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { detectedLanguage, englishOf, type AnswerLanguage } from "@/lib/answerLanguages";
import type { DepthOption } from "@/lib/askConfig";
import { craftOffer, type CraftOption, type CraftPick } from "@/lib/askCraft";
import { isDepth } from "@/lib/askDepth";
import type { Depth, Understood } from "@/lib/explainerContract";
import type { UnderstoodPart } from "@/lib/explainerView";

export type AskOptionsProps = {
  understood: Understood | null;
  craft: { pick: CraftPick; options: CraftOption[]; onPick: (pick: CraftPick) => void };
  depth: { value: Depth | null; options: DepthOption[]; onPick: (depth: Depth) => void };
  language: { choice: string; languages: AnswerLanguage[]; question: string; onPick: (choice: string) => void };
};

export const ASK_OPTION_IDS: Record<UnderstoodPart, string> = { craft: "ask-craft", depth: "ask-depth", language: "ask-language" };

export function focusAskOption(part: UnderstoodPart): void {
  const control = document.getElementById(ASK_OPTION_IDS[part]);
  (control?.querySelector<HTMLElement>('button[aria-pressed="true"]') ?? control?.querySelector<HTMLElement>("button"))?.focus();
}

export function AskOptions({ understood, craft, depth, language }: AskOptionsProps) {
  const detected = detectedLanguage(language.question, language.languages) ?? englishOf(language.languages);
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-3" data-testid="ask-options">
      <div id={ASK_OPTION_IDS.craft} className="contents">
        <CraftChoice pick={craft.pick} options={craft.options} offer={craftOffer(understood, craft.pick)} onPick={craft.onPick} />
      </div>
      {depth.value !== null && depth.options.length > 1 ? (
        <div id={ASK_OPTION_IDS.depth} className="contents">
          <SegmentedChoice
            label="Depth"
            value={depth.value}
            options={depth.options.map((option) => ({ value: option.depth, label: option.label }))}
            onChange={(next) => {
              if (isDepth(next)) depth.onPick(next);
            }}
          />
        </div>
      ) : null}
      {language.languages.length > 1 ? (
        <div id={ASK_OPTION_IDS.language} className="flex min-w-0 items-center gap-2">
          <span className="font-ui text-label text-ink-3">Answer in</span>
          <LanguagePicker value={language.choice} languages={language.languages} detected={detected} onChange={language.onPick} />
        </div>
      ) : null}
    </div>
  );
}
