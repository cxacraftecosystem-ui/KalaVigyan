import Link from "next/link";

import { fieldsFinding, type FieldHolding, type FieldHoldings } from "@/components/landing/fieldHoldings";
import { TextLink } from "@/components/ui/TextLink";
import { DISCIPLINES } from "@/lib/explainerBlockBase";
import { DISCIPLINE_LABEL } from "@/lib/explainerView";

export const FIELDS_HEADING = "Sixteen fields";

export function fieldsDek(holdings: FieldHoldings | null): string {
  if (!holdings) return "Each craft is read across the same sixteen fields, from how it is made to the policy around it, and every sentence carries its sources.";
  return `Each count is the number of the ${holdings.monographs} monographs that hold cited facts in a field; the craft holding the most opens at that field’s chapter.`;
}

export function leadLine(holding: FieldHolding): string | null {
  if (!holding.lead) return null;
  return `${holding.lead.facts} cited ${holding.lead.facts === 1 ? "fact" : "facts"}`;
}

export function fieldNumber(at: number): string {
  return String(at + 1).padStart(2, "0");
}

function FieldCell({ holding, total, at }: { holding: FieldHolding; total: number; at: number }) {
  const share = total > 0 ? holding.crafts / total : 0;
  const facts = leadLine(holding);
  return (
    <li className="kv-field" data-testid="landing-field">
      <p className="kv-field-head">
        <span className="kv-field-no" aria-hidden>
          {fieldNumber(at)}
        </span>
        <span className="kv-field-name">{holding.label}</span>
      </p>
      <p className="kv-field-count">
        <b>{holding.crafts}</b>
        <span>{` of ${total} monographs`}</span>
      </p>
      <span className="kv-field-bar" aria-hidden>
        <i style={{ width: `${(share * 100).toFixed(1)}%` }} />
      </span>
      {holding.lead ? (
        <p className="kv-field-lead">
          Most in{" "}
          <Link href={holding.lead.href} className="kv-link font-normal">
            {holding.lead.name}
          </Link>
          {facts ? `, ${facts}` : null}
        </p>
      ) : null}
    </li>
  );
}

function PlainFields() {
  return (
    <ul className="mt-8 grid gap-x-12 sm:grid-cols-2 lg:grid-cols-4" data-testid="landing-fields-plain">
      {DISCIPLINES.map((field) => (
        <li key={field} className="border-t border-rule py-2.5 font-ui text-ui font-medium text-ink-1">
          {DISCIPLINE_LABEL[field]}
        </li>
      ))}
    </ul>
  );
}

export function FieldsSection({ holdings }: { holdings: FieldHoldings | null }) {
  const finding = holdings ? fieldsFinding(holdings) : null;
  return (
    <section id="fields" className="scroll-mt-6 border-t border-rule py-section" aria-labelledby="fields-h" data-testid="landing-fields">
      <div className="kv-shell-wrap">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:items-end lg:gap-16">
          <div className="min-w-0">
            <p className="kv-chapter-no">Every field</p>
            <h2 id="fields-h" className="m-0 font-headline text-h2 text-ink-1">
              {FIELDS_HEADING}
            </h2>
          </div>
          <div className="min-w-0">
            {finding ? <p className="font-reading text-h3 text-ink-1 [font-variant-numeric:lining-nums] [text-wrap:balance]">{finding}</p> : null}
            <p className="mt-2 max-w-measure font-ui text-ui text-ink-2">{fieldsDek(holdings)}</p>
          </div>
        </div>
        {holdings ? (
          <ol className="kv-field-index" aria-label="Monographs holding cited facts in each field" data-testid="landing-field-list">
            {holdings.fields.map((holding, at) => (
              <FieldCell key={holding.field} holding={holding} total={holdings.monographs} at={at} />
            ))}
          </ol>
        ) : (
          <PlainFields />
        )}
        <p className="mt-6">
          <TextLink href="/crafts" standalone>
            Find a craft in the atlas
          </TextLink>
        </p>
      </div>
    </section>
  );
}
