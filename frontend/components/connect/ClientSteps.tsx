import { CopyCode } from "@/components/connect/CopyCode";
import { TextLink } from "@/components/ui/TextLink";
import type { ClientGuide } from "@/lib/connectClients";

export const STEP_LIST = "m-0 grid list-decimal gap-4 ps-6 font-ui text-ui font-normal marker:font-ui marker:text-label marker:text-ink-3";

function ClientCard({ guide }: { guide: ClientGuide }) {
  const heading = `client-${guide.key}`;
  return (
    <article aria-labelledby={heading} className="grid min-w-0 content-start gap-4 border-t border-ink-1 pt-4" data-testid={`client-${guide.key}`}>
      <h3 id={heading} className="font-reading text-h3 text-ink-1">
        {guide.name}
      </h3>
      <ol className={STEP_LIST}>
        {guide.steps.map((step) => (
          <li key={step.text} className="min-w-0 ps-1">
            <div className="grid min-w-0 gap-2">
              <p className="m-0 font-ui text-ui font-normal text-ink-1">{step.text}</p>
              {step.code ? <CopyCode code={step.code} /> : null}
            </div>
          </li>
        ))}
      </ol>
      {guide.note ? <p className="m-0 font-ui text-label text-ink-2">{guide.note}</p> : null}
      <p className="m-0 font-ui text-label">
        <TextLink href={guide.docs} external>
          {guide.name} documentation
        </TextLink>
      </p>
    </article>
  );
}

export function ClientSteps({ guides }: { guides: readonly ClientGuide[] }) {
  return (
    <div className="grid gap-x-10 gap-y-10 md:grid-cols-2 xl:grid-cols-3">
      {guides.map((guide) => (
        <ClientCard key={guide.key} guide={guide} />
      ))}
    </div>
  );
}
