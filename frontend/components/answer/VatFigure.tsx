"use client";

import { useRef, useState } from "react";

import { CitedText } from "@/components/answer/ProseBlockView";
import { ExplainerSentence } from "@/components/answer/ExplainerSentence";
import { VatArt, type VatArtRefs } from "@/components/answer/VatArt";
import { VatEquationView } from "@/components/answer/VatEquation";
import { FactGrid } from "@/components/editorial/FactGrid";
import { motionAllowedNow } from "@/components/motion/useMotionAllowed";
import { useVatMoment } from "@/components/motion/useVatMoment";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { Figure } from "@/components/ui/Figure";
import { currentFrame, dipStatus, nextDip, vatEquation, vatFrames, VAT_DIPS, type VatFrame } from "@/lib/answerVat";
import type { IndigoVatBlock } from "@/lib/explainerSignature";
import { cn } from "@/lib/utils";

function replay(element: Element | null): void {
  if (!element || !motionAllowedNow()) return;
  element.removeAttribute("data-playing");
  void element.getBoundingClientRect();
  element.setAttribute("data-playing", "");
  element.addEventListener("animationend", () => element.removeAttribute("data-playing"), { once: true });
}

function Frames({ frames, current, dip, dipRef, airRef }: VatArtRefs & { frames: VatFrame[]; current: VatFrame["key"]; dip: number }) {
  return (
    <ol className="grid grid-cols-1 overflow-hidden rounded-plate border border-ink-1 md:grid-cols-3" data-testid="vat-frames">
      {frames.map((frame, index) => {
        const on = frame.key === current;
        return (
          <li
            key={frame.key}
            aria-current={on ? "step" : undefined}
            className={cn(
              "relative grid min-w-0 grid-cols-[112px_minmax(0,1fr)] content-start gap-x-3.5 bg-raised pb-3 pe-3.5 md:block md:pb-4.5 md:pe-0",
              index > 0 ? "border-t border-rule md:border-t-0 md:border-s" : null
            )}
            data-frame={frame.key}
          >
            {on ? <span aria-hidden className="absolute inset-x-0 top-0 h-0.5 bg-ink-1" /> : null}
            <div className="row-span-3">
              <VatArt frame={frame.key} dip={dip} dipRef={dipRef} airRef={airRef} />
            </div>
            <p className="mt-1 font-ui text-caption font-semibold tabular-nums text-ink-3 md:mx-4.5 md:mt-3">{index + 1}</p>
            <h3 className={cn("mt-1 font-reading text-body text-ink-1 md:mx-4.5 md:text-h3", on ? "font-semibold" : null)}>{frame.title}</h3>
            {frame.sentence ? <CitedText id={`vat-${frame.key}`} sentences={[frame.sentence]} className="mt-1.5 font-reading text-figcaption text-ink-2 md:mx-4.5 md:text-body-sm" /> : null}
          </li>
        );
      })}
    </ol>
  );
}

function VatFacts({ block }: { block: IndigoVatBlock }) {
  const facts = [
    ...block.contents.map((content) => ({ label: content.name, value: <ExplainerSentence sentence={content.sentence} /> })),
    ...block.dips.slice(1).map((dip) => ({ label: `${dip.stated}${dip.shade ? `, ${dip.shade}` : ""}`, value: <ExplainerSentence sentence={dip.sentence} /> }))
  ];
  if (facts.length === 0) return null;
  return (
    <section className="mt-6" aria-label={block.vat === "FERMENTED" ? "What the fermented vat holds" : "What the vat holds"}>
      <p className="kicker mb-2">{block.vat === "FERMENTED" ? "A fermented vat holds" : "A chemical vat holds"}</p>
      <FactGrid facts={facts} columns={2} />
    </section>
  );
}

export function VatFigure({ block, number }: { block: IndigoVatBlock; number: number }) {
  const [dip, setDip] = useState(1);
  const dipRef = useRef<SVGGElement | null>(null);
  const airRef = useRef<SVGGElement | null>(null);
  const vat = useVatMoment({
    onPhase: (phase) => {
      if (phase === "in") {
        setDip(nextDip);
        replay(dipRef.current);
      }
      if (phase === "air") replay(airRef.current);
    }
  });
  const leuco = block.forms.find((form) => form.form === "LEUCO");
  const keto = block.forms.find((form) => form.form === "KETO");
  const equation = leuco && keto ? vatEquation({ formula: leuco.compound?.formula ?? null, name: leuco.name }, { formula: keto.compound?.formula ?? null, name: keto.name }) : null;
  const restart = vat.phase === "rest" && dip >= VAT_DIPS;
  const dek = block.dips[0] ? <ExplainerSentence sentence={block.dips[0].sentence} /> : undefined;
  return (
    <Figure number={number} kind="diagram" title="One dip, three states" dek={dek} className="kv-vat" id="fig-vat">
      <div className="grid grid-cols-1 gap-7 rail:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] rail:items-start rail:gap-12" data-testid="vat-figure" data-dip={dip} data-phase={vat.phase}>
        <Frames frames={vatFrames(block)} current={currentFrame(vat.phase)} dip={dip} dipRef={dipRef} airRef={airRef} />
        <div className="min-w-0">
          <div className="grid justify-items-center gap-3 text-center rail:border-b rail:border-rule rail:pb-5.5 rail:pt-4.5">
            <p role="status" aria-live="polite" className="min-h-[1.5em] font-ui text-ui font-normal text-ink-2" data-testid="vat-status">
              {dipStatus(dip, vat.phase)}
            </p>
            <ActionGroup>
              <Button variant="quiet" onClick={vat.play} data-testid="vat-dip">
                {restart ? "Start again" : "Dip again"}
              </Button>
            </ActionGroup>
          </div>
          {equation ? <VatEquationView equation={equation} leuco={leuco} keto={keto} /> : null}
          <VatFacts block={block} />
        </div>
      </div>
    </Figure>
  );
}
