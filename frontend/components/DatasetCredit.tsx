import { safeOutboundUrl } from "@/lib/citations";
import type { RegionDataset } from "@/lib/regionContract";

const LINK = "kv-link font-normal";

export function DatasetCredit({ dataset, methods = [] }: { dataset: RegionDataset; methods?: readonly string[] }) {
  const href = safeOutboundUrl(dataset.url);
  const licenceHref = safeOutboundUrl(dataset.licenceUrl);
  return (
    <span className="grid gap-0.5 font-ui text-caption text-ink-3" data-testid="dataset-credit">
      <span>
        {href ? (
          <a href={href} target="_blank" rel="noopener noreferrer" className={LINK}>
            {dataset.title}
          </a>
        ) : (
          <span className="font-medium text-ink-2">{dataset.title}</span>
        )}
        {[dataset.publisher, dataset.edition].filter(Boolean).map((part) => ` · ${part}`)}
      </span>
      <span>
        {licenceHref ? (
          <a href={licenceHref} target="_blank" rel="noopener noreferrer" className={LINK}>
            {dataset.licence}
          </a>
        ) : (
          dataset.licence
        )}
        {dataset.attribution ? ` · ${dataset.attribution}` : null}
      </span>
      {dataset.citation ? <span>{dataset.citation}</span> : null}
      {methods.map((method) => (
        <span key={method}>Method: {method}</span>
      ))}
    </span>
  );
}
