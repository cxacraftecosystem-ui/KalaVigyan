export function ReviewTerm({ term, value, lang, script }: { term: string; value: string; lang?: string; script?: string }) {
  return (
    <div className="grid gap-0.5">
      <dt className="text-ink-3">{term}</dt>
      <dd className="text-ink-1 [overflow-wrap:anywhere]" lang={lang} data-script={script}>
        {value}
      </dd>
    </div>
  );
}
