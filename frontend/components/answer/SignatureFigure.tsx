"use client";

import { ExplainerSentence } from "@/components/answer/ExplainerSentence";
import { VatFigure } from "@/components/answer/VatFigure";
import { FactGrid, type Fact } from "@/components/editorial/FactGrid";
import { Figure } from "@/components/ui/Figure";
import { firingTitle, lostWaxTitle, mordantLabel, mordantTitle, signatureStepLabel } from "@/lib/answerSignature";
import type { FiringBlock, LostWaxBlock, MordantBathBlock, SignatureBlock } from "@/lib/explainerSignature";

function MordantFigure({ block, number }: { block: MordantBathBlock; number: number }) {
  const facts: Fact[] = block.swatches.map((swatch) => ({ label: mordantLabel(swatch), value: <ExplainerSentence sentence={swatch.sentence} /> }));
  return (
    <Figure number={number} kind="diagram" title={mordantTitle(block)} id="fig-signature">
      <FactGrid facts={facts} columns={facts.length > 2 ? 4 : 2} />
    </Figure>
  );
}

function LostWaxFigure({ block, number }: { block: LostWaxBlock; number: number }) {
  return (
    <Figure number={number} kind="diagram" title={lostWaxTitle(block)} id="fig-signature">
      <ol className="grid grid-cols-1 border-t border-ink-1 sm:grid-cols-2 lg:grid-cols-5" data-testid="lost-wax-steps">
        {block.steps.map((step, index) => (
          <li key={step.step} className="min-w-0 border-b border-rule py-3.5 sm:pe-6">
            <p className="font-ui text-caption font-semibold tabular-nums text-ink-3">{index + 1}</p>
            <h3 className="mt-1 font-reading text-h3 text-ink-1">{signatureStepLabel(step.step)}</h3>
            <p className="mt-1.5 font-reading text-body-sm text-ink-2">
              <ExplainerSentence sentence={step.sentence} />
            </p>
          </li>
        ))}
      </ol>
    </Figure>
  );
}

function FiringFigure({ block, number }: { block: FiringBlock; number: number }) {
  const facts: Fact[] = [
    ...block.atmospheres.map((atmosphere) => ({ label: signatureStepLabel(atmosphere.atmosphere, atmosphere.colour), value: <ExplainerSentence sentence={atmosphere.sentence} /> })),
    ...(block.temperature ? [{ label: `Temperature, ${block.temperature.stated}`, value: <ExplainerSentence sentence={block.temperature.sentence} /> }] : [])
  ];
  return (
    <Figure number={number} kind="diagram" title={firingTitle(block)} id="fig-signature">
      <FactGrid facts={facts} columns={facts.length > 2 ? 4 : 2} />
    </Figure>
  );
}

export function SignatureFigure({ block, number }: { block: SignatureBlock; number: number }) {
  if (block.kind === "indigo_vat") return <VatFigure block={block} number={number} />;
  if (block.kind === "mordant_bath") return <MordantFigure block={block} number={number} />;
  if (block.kind === "lost_wax") return <LostWaxFigure block={block} number={number} />;
  return <FiringFigure block={block} number={number} />;
}
