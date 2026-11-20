import Link from "next/link";

import { fieldsFinding, type FieldHolding, type FieldHoldings } from "@/components/landing/fieldHoldings";
import { TextLink } from "@/components/ui/TextLink";
import { DISCIPLINES } from "@/lib/explainerBlockBase";
import { DISCIPLINE_LABEL } from "@/lib/explainerView";

export const FIELDS_HEADING = "Sixteen fields";

export function fieldsDek(holdings: FieldHoldings | null): string {
  if (!holdings) return "Each craft is read across the same sixteen fields, from how it is made to the policy around it, and every sentence carries its sources.";
  return `Each bar counts the ${holdings.monographs} monographs that hold cited facts in a field; the craft holding the most opens at that field’s chapter.`;
}

export function leadLine(holding: FieldHolding): string | null {
  if (!holding.lead) return null;
  return `${holding.lead.facts} cited ${holding.lead.facts === 1 ? "fact" : "facts"}`;
}

function FieldRow({ holding, total }: { holding: FieldHolding; total: number }) {
  const share = total > 0 ? holding.crafts / total : 0;
  const facts = leadLine(holding);
  return (
    <li className="grid grid-cols-[minmax(7.5rem,10rem)_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 border-t border-rule py-2.5" data-testid="landing-field">
      <span className="font-ui text-ui font-medium text-ink-1">{holding.label}</span>
      <span className="relative h-2 bg-rule" aria-hidden>
        <i className="absolute inset-y-0 start-0" style={{ width: `${(share * 100).toFixed(1)}%`, backgroundColor: "var(--series-count)" }} />
      </span>
      <b className="text-end font-ui text-ui font-medium text-ink-2 [font-variant-numeric:lining-nums_tabular-nums]">
        {holding.crafts}
        <span className="sr-only">{` of ${total} monographs`}</span>
      </b>
      {holding.lead ? (
        <p className="col-span-3 font-ui text-label text-ink-3">
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
          <ol className="mt-8 grid border-b border-rule md:grid-cols-2 md:gap-x-12" aria-label="Monographs holding cited facts in each field" data-testid="landing-field-list">
            {holdings.fields.map((holding) => (
              <FieldRow key={holding.field} holding={holding} total={holdings.monographs} />
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
