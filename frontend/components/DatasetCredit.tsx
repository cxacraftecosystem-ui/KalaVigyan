import { safeOutboundUrl } from "@/lib/citations";
import { datasetReadLine } from "@/lib/datasetRecord";
import type { RegionDataset } from "@/lib/regionContract";

const LINK = "kv-link font-normal";
const DOI_ORIGIN = "https://doi.org/";
const SHOWN_ONLY = "Shown on the site's maps only, never as a download or an export.";

function Linked({ href, text }: { href: string | null | undefined; text: string }) {
  const safe = safeOutboundUrl(href ?? null);
  if (!safe) return <span className="font-medium text-ink-2">{text}</span>;
  return (
    <a href={safe} target="_blank" rel="noopener noreferrer" className={LINK}>
      {text}
    </a>
  );
}

export function DatasetCredit({ dataset, methods = [] }: { dataset: RegionDataset; methods?: readonly string[] }) {
  const read = datasetReadLine(dataset);
  const doi = dataset.doi && !(dataset.citation ?? "").includes(dataset.doi) ? dataset.doi : null;
  return (
    <span className="grid gap-0.5 font-ui text-caption text-ink-3" data-testid="dataset-credit">
      <span>
        <Linked href={dataset.landingUrl ?? dataset.url} text={dataset.title} />
        {[dataset.publisher, dataset.version ?? dataset.edition].filter(Boolean).map((part) => ` · ${part}`)}
      </span>
      <span>
        {dataset.licenceUrl ? <Linked href={dataset.licenceUrl} text={dataset.licence} /> : dataset.licence}
        {dataset.attribution ? ` · ${dataset.attribution}` : null}
      </span>
      {dataset.citation ? <span>{dataset.citation}</span> : null}
      {doi ? <Linked href={`${DOI_ORIGIN}${doi}`} text={`doi:${doi}`} /> : null}
      {read ? <span>{read}</span> : null}
      {dataset.redistributable === false ? <span>{SHOWN_ONLY}</span> : null}
      {methods.map((method) => (
        <span key={method}>Method: {method}</span>
      ))}
    </span>
  );
}
