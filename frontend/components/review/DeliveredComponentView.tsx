import { ComponentSlot } from "@/components/monograph/ComponentSlot";
import { FactSources } from "@/components/review/FactEvidence";
import { MONOGRAPH_KIT_CSS } from "@/lib/monographDocument";
import type { DeliveredFact, DeliveredReview, DeliveredUnitReview } from "@/lib/reviewQueueContract";
import { deliveredFactLine, factNumbersLine } from "@/lib/reviewQueueView";

export function DeliveredComponentView({ label, delivery }: { label: string; delivery: DeliveredReview }) {
  const numbers = new Map(delivery.facts.map((fact, index) => [fact.id, index + 1]));
  return (
    <section className="grid gap-5" data-testid="delivered-component">
      <div className="grid gap-2">
        <h4 className="font-ui text-h4 text-ink-1">As the page will draw it</h4>
        {delivery.drawing ? (
          <div className="kv-monograph min-w-0 overflow-x-auto border-t border-ink-1 pt-4" lang={delivery.drawing.language}>
            <link rel="stylesheet" href={MONOGRAPH_KIT_CSS} precedence="default" />
            <ComponentSlot document={delivery.drawing} label={label} />
          </div>
        ) : (
          <p className="max-w-measure font-ui text-ui text-ink-2">It is drawn once every fact it rests on is shown on the page; the facts below say which are held.</p>
        )}
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <DeliveredUnits units={delivery.units} numbers={numbers} />
        <DeliveredFacts facts={delivery.facts} />
      </div>
    </section>
  );
}

function DeliveredUnits({ units, numbers }: { units: DeliveredUnitReview[]; numbers: ReadonlyMap<string, number> }) {
  return (
    <section className="grid content-start gap-2">
      <h4 className="font-ui text-h4 text-ink-1">Its text, unit by unit</h4>
      <ol className="grid gap-3">
        {units.map((unit) => (
          <li key={unit.unit} className="grid gap-0.5 border-t border-rule pt-2">
            <p className="font-code text-caption text-ink-3">{unit.unit}</p>
            <p className="font-reading text-body-sm text-ink-1">{unit.text}</p>
            <p className="font-ui text-label text-ink-2">{factNumbersLine(unit.claimIds, numbers)}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

function DeliveredFacts({ facts }: { facts: DeliveredFact[] }) {
  return (
    <section className="grid content-start gap-2">
      <h4 className="font-ui text-h4 text-ink-1">The facts it rests on</h4>
      <ol className="grid gap-4">
        {facts.map((fact, index) => (
          <li key={fact.id} className="grid gap-2 border-t border-rule pt-2">
            <p className="font-ui text-label text-ink-3">{deliveredFactLine(index + 1, fact)}</p>
            <p className="font-reading text-body-sm text-ink-1">{fact.text}</p>
            {fact.sources.length ? <FactSources sources={fact.sources} /> : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
