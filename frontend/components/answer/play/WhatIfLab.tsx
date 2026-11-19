"use client";

import { useState } from "react";
import { CircleHelp } from "lucide-react";

import { ExplainerSentence } from "@/components/answer/ExplainerSentence";
import type { WhatIfBlock, WhatIfOption } from "@/lib/explainerPlay";
import { cn } from "@/lib/utils";
import { isUnknownOption, optionNote, UNKNOWN_OUTCOME } from "@/lib/whatIfView";

function OptionButton({ option, on, onPick }: { option: WhatIfOption; on: boolean; onPick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onPick}
      className={cn(
        "flex min-h-target min-w-0 flex-col items-start gap-0.5 rounded-control border px-3 py-2 text-start font-ui transition-colors duration-state",
        on ? "border-indigo bg-indigo-wash text-indigo-hover" : "border-rule-strong bg-raised text-ink-1 hover:border-ink-1"
      )}
      data-testid="what-if-option"
      data-unknown={isUnknownOption(option)}
    >
      <span className="min-w-0 max-w-full break-words text-ui font-semibold">{option.label}</span>
      <span className={cn("text-label font-normal", on ? "text-indigo-hover" : "text-ink-3")}>{optionNote(option)}</span>
    </button>
  );
}

function Outcomes({ option }: { option: WhatIfOption }) {
  if (isUnknownOption(option)) {
    return (
      <p className="flex items-center gap-1.5 font-ui text-ui font-semibold text-ink-2" data-testid="what-if-unknown">
        <CircleHelp className="h-4 w-4 shrink-0 text-ink-3" aria-hidden />
        {UNKNOWN_OUTCOME}
      </p>
    );
  }
  return (
    <ul className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-2">
      {option.outcomes.map((outcome) => (
        <li key={outcome.sentence.id} className="min-w-0 max-w-measure break-words font-reading text-body-sm text-ink-1" data-testid="what-if-outcome">
          <ExplainerSentence sentence={outcome.sentence} />
        </li>
      ))}
    </ul>
  );
}

export function WhatIfLabView({ block }: { block: WhatIfBlock; reduce?: boolean }) {
  const [chosen, setChosen] = useState(0);
  const option = block.options[chosen];
  const titleId = `${block.id}-title`;
  return (
    <section className="kv-figure grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4" aria-labelledby={titleId} data-testid="what-if" data-chosen={chosen + 1}>
      <header className="min-w-0">
        <p className="kicker">What if</p>
        <h3 id={titleId} className="mt-1 break-words font-reading text-h3 text-ink-1">
          {block.changed}
        </h3>
      </header>
      <div role="group" aria-labelledby={titleId} className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-2 sm:grid-cols-[repeat(2,minmax(0,1fr))] lg:grid-cols-[repeat(3,minmax(0,1fr))]">
        {block.options.map((entry, index) => (
          <OptionButton key={entry.label} option={entry} on={index === chosen} onPick={() => setChosen(index)} />
        ))}
      </div>
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-2 bg-sunk p-4" aria-live="polite" data-testid="what-if-outcomes">
        <p className="kicker min-w-0 break-words">{option.label}</p>
        <Outcomes option={option} />
      </div>
    </section>
  );
}

export function WhatIfLab({ block }: { block: WhatIfBlock }) {
  return <WhatIfLabView block={block} />;
}
