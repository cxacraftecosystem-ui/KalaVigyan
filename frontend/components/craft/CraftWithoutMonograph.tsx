import Link from "next/link";

import { FactGrid } from "@/components/editorial/FactGrid";
import { Masthead } from "@/components/editorial/Masthead";
import { TypographicPlate } from "@/components/editorial/TypographicPlate";
import { EmptyState } from "@/components/EmptyState";
import { buttonLook } from "@/components/ui/button";
import { RECORD_HEADING, RECORD_KICKER, START_BODY, type CraftRecordView } from "@/lib/craftRecord";

export function CraftWithoutMonograph({ record }: { record: CraftRecordView }) {
  const plate = <TypographicPlate material={record.material} englishName={record.name} nativeName={record.nativeName} size="small" decorative />;
  const provenance = record.provenance.map((part) => <span key={part}>{part}</span>);
  return (
    <article lang="en" data-testid="craft-without-monograph">
      <div className="kv-unc-head">
        <Masthead
          material={record.material}
          plateKicker={record.plateKicker}
          label={{ kicker: RECORD_KICKER, family: record.family, name: record.name, nativeName: record.nativeName, gi: record.gi, place: record.place, provenance }}
        />
      </div>
      <div className="kv-unc-body">
        {record.facts.length ? (
          <section className="kv-unc-facts" aria-labelledby="craft-record-h">
            <h2 id="craft-record-h" className="kicker">
              {RECORD_HEADING}
            </h2>
            <FactGrid facts={record.facts} />
          </section>
        ) : null}
        <section className="kv-unc-start">
          <EmptyState
            plate={plate}
            title={record.start}
            body={START_BODY}
            actions={record.questions.map((question) => (
              <Link key={question.href} href={question.href} {...buttonLook({ variant: "quiet", size: "sm" })}>
                {question.question}
              </Link>
            ))}
          />
        </section>
      </div>
    </article>
  );
}
