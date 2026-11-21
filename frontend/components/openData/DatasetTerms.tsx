import { OpenDataSection } from "@/components/openData/OpenDataSection";
import { TextLink } from "@/components/ui/TextLink";
import type { OpenDataListing } from "@/lib/openDataContract";
import { licenceLabel } from "@/lib/openDataView";

export const TERMS_TITLE = "Reuse and its limits";

export function DatasetTerms({ listing }: { listing: OpenDataListing }) {
  return (
    <OpenDataSection id="open-data-terms" title={TERMS_TITLE}>
      <div className="grid min-w-0 gap-8 lg:grid-cols-2 lg:gap-10">
        <div className="grid content-start gap-4">
          <h3 className="font-reading text-h3 text-ink-1">The licence</h3>
          <p className="max-w-measure font-reading text-body text-ink-1">
            KalaVigyan&apos;s own sentences and structure in this dataset are licensed under{" "}
            <TextLink href={listing.licence.url} external>
              {listing.licence.name} ({licenceLabel(listing.licence.id)})
            </TextLink>
            : copy, adapt and share them for any purpose, with this attribution.
          </p>
          <p className="max-w-measure border-s-2 border-rule-strong ps-4 font-reading text-body-sm text-ink-2">{listing.attribution}</p>
          <p className="max-w-measure font-reading text-body text-ink-1">{listing.citedWorks}</p>
          <p className="font-ui text-label text-ink-3">
            The code that builds every release:{" "}
            <TextLink href={listing.codeUrl} external>
              {listing.codeUrl.replace("https://", "")}
            </TextLink>
          </p>
        </div>
        <div className="grid content-start gap-4">
          <h3 className="font-reading text-h3 text-ink-1">What stays out</h3>
          <ul className="grid gap-3 border-t border-rule pt-3">
            {listing.leftOut.map((item) => (
              <li key={item} className="max-w-measure border-b border-rule pb-3 font-reading text-body-sm text-ink-1">
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </OpenDataSection>
  );
}
