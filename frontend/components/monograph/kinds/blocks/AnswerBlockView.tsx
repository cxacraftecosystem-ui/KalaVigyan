"use client";

import { useMemo } from "react";

import { renderBlock } from "@/components/answer/blockRenderers";
import { CitedReading } from "@/components/answer/CitedReading";
import { SignatureFigure } from "@/components/answer/SignatureFigure";
import { blockColumn, blockFrame, parseAnswerBlockSpec, sourceNumbers, type AnswerBlockSpec } from "@/components/monograph/kinds/blocks/answerBlockSpec";
import { useMonographSlot } from "@/components/monograph/MonographSlotContext";
import { Figure } from "@/components/ui/Figure";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { figureKicker } from "@/lib/editorialText";
import type { SignatureBlock } from "@/lib/explainerSignature";

import "./answerBlock.css";

const NO_NUMBERS: ReadonlyMap<string, number> = new Map();

function FigureNumber({ kind, number }: { kind: "figure" | "table"; number: number }) {
  const [word, digits] = figureKicker(kind, number).split(" ");
  return (
    <p className="kv-fig-no">
      {word} <b>{digits}</b>
    </p>
  );
}

function FramedBlock({ spec }: { spec: AnswerBlockSpec }) {
  const frame = blockFrame(spec);
  const figure = spec.figure;
  if (frame === "signature") return <SignatureFigure block={spec.block as SignatureBlock} number={figure?.number ?? 1} />;
  const drawn = renderBlock(spec.block);
  if (!figure || frame === "bare") return drawn;
  const table = figure.kind === "TABLE";
  if (frame === "numbered") {
    return (
      <>
        <FigureNumber kind={table ? "table" : "figure"} number={figure.number} />
        {drawn}
      </>
    );
  }
  return (
    <Figure number={figure.number} kind={table ? "table" : "diagram"} title={figure.title}>
      {drawn}
    </Figure>
  );
}

export function AnswerBlockView({ spec }: ComponentViewProps) {
  const parsed = useMemo(() => parseAnswerBlockSpec(spec), [spec]);
  const { sources } = useMonographSlot();
  const numbers = useMemo(() => (parsed ? sourceNumbers(parsed, sources) : new Map(NO_NUMBERS)), [parsed, sources]);
  const refs = useMemo(() => parsed?.sources.map((source) => source.ref) ?? [], [parsed]);
  if (!parsed) return null;
  return (
    <CitedReading sources={refs} numbers={numbers}>
      <div className="spread">
        <div className={blockColumn(parsed)}>
          <div className="kv-answer-block min-w-0 font-reading text-ink-1" data-block-kind={parsed.block.kind} data-testid="answer-block">
            <FramedBlock spec={parsed} />
          </div>
        </div>
      </div>
    </CitedReading>
  );
}
