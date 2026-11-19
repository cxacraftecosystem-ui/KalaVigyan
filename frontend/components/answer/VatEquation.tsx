import { Fragment } from "react";

import { formulaParts, pubchemHref, type Species, type VatEquation as Equation } from "@/lib/answerVat";
import type { IndigoForm } from "@/lib/explainerSignature";

function Formula({ formula }: { formula: string }) {
  return formulaParts(formula).map((part, index) => (
    <Fragment key={`${part.symbol}${index}`}>
      {part.symbol}
      {part.count ? <sub>{part.count}</sub> : null}
    </Fragment>
  ));
}

function SpeciesTerm({ species, note }: { species: Species; note: string }) {
  return (
    <span className="inline-grid gap-1">
      <b className="whitespace-nowrap font-reading text-body font-medium lining-nums text-ink-1 sm:text-h3">
        {species.coefficient > 1 ? `${species.coefficient} ` : null}
        <Formula formula={species.formula} />
      </b>
      <small className="max-w-[15ch] font-ui text-caption text-ink-3">{note}</small>
    </span>
  );
}

function Side({ side, notes, arrow }: { side: Species[]; notes: string[]; arrow: boolean }) {
  return (
    <span className="inline-flex max-w-full flex-nowrap items-start gap-3 whitespace-nowrap">
      {arrow ? <span className="font-reading text-body text-ink-3 sm:text-h3">→</span> : null}
      {side.map((species, index) => (
        <Fragment key={species.formula}>
          {index > 0 ? <span className="font-reading text-body text-ink-3 sm:text-h3">+</span> : null}
          <SpeciesTerm species={species} note={notes[index] ?? species.name} />
        </Fragment>
      ))}
    </span>
  );
}

function formNote(form: IndigoForm | undefined, fallback: string): string {
  if (!form) return fallback;
  return `${form.name}, ${form.soluble ? "dissolved" : "insoluble"}`;
}

function AtomTable({ equation }: { equation: Equation }) {
  return (
    <table className="font-ui text-label tabular-nums text-ink-1" data-testid="vat-atoms">
      <caption className="kicker pb-1.5 text-start">Count the atoms</caption>
      <thead>
        <tr className="border-b border-ink-1 text-ink-3">
          {["Atom", "Before", "After"].map((label) => (
            <th key={label} scope="col" className="py-1.5 pe-3.5 text-start font-medium">
              {label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {equation.rows.map((row) => (
          <tr key={row.atom} className="border-b border-rule">
            <th scope="row" className="py-1.5 pe-3.5 text-start font-reading text-figcaption font-semibold">
              {row.atom}
            </th>
            <td className="whitespace-nowrap py-1.5 pe-3.5">{row.before}</td>
            <td className="whitespace-nowrap py-1.5 pe-3.5">{row.after}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function VatEquationView({ equation, leuco, keto }: { equation: Equation; leuco: IndigoForm | undefined; keto: IndigoForm | undefined }) {
  const cids = [leuco, keto].flatMap((form) => (form?.compound ? [form.compound.pubchemCid] : []));
  return (
    <div className="mt-6 border-t border-ink-1 pt-4 rail:mt-5 rail:border-t-0 rail:pt-0" role="group" aria-label={equation.spoken} data-testid="vat-equation">
      <div className="flex flex-wrap items-start gap-x-3.5 gap-y-3">
        <Side side={equation.reactants} notes={[formNote(leuco, equation.reactants[0].name), "oxygen, from the air"]} arrow={false} />
        <Side side={equation.products} notes={[formNote(keto, equation.products[0].name), "water"]} arrow />
      </div>
      <div className="mt-4 grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-end">
        <AtomTable equation={equation} />
        <p className="max-w-[44ch] font-ui text-label text-ink-3">
          Formulas from PubChem
          {cids.map((cid, index) => (
            <Fragment key={cid}>
              {index === 0 ? " " : " and "}
              <a href={pubchemHref(cid)} target="_blank" rel="noopener noreferrer" className="kv-link">
                CID {cid}
                <span className="sr-only"> (opens in a new tab)</span>
              </a>
            </Fragment>
          ))}
          ; the atoms balance.
        </p>
      </div>
    </div>
  );
}
