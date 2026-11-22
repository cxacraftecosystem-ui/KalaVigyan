import type { ReactNode } from "react";

import { FactGrid } from "@/components/editorial/FactGrid";
import { CraftReleases } from "@/components/openData/CraftReleases";
import { DatasetCitation } from "@/components/openData/DatasetCitation";
import { DatasetTerms } from "@/components/openData/DatasetTerms";
import { OpenDataSection } from "@/components/openData/OpenDataSection";
import { ReleaseHistory } from "@/components/openData/ReleaseHistory";
import { TableHoldings } from "@/components/openData/TableHoldings";
import { TextLink } from "@/components/ui/TextLink";
import type { OpenDataListing } from "@/lib/openDataContract";
import { glanceFacts, tableHoldings, type GlanceFact } from "@/lib/openDataView";

export const OPEN_DATA_KICKER = "Open data";
export const HOLDINGS_TITLE = "What it holds";
export const HISTORY_TITLE = "Releases";

function factValue(fact: GlanceFact): ReactNode {
  if (!fact.href) return <span className="lining-nums tabular-nums">{fact.value}</span>;
  return (
    <TextLink href={fact.href} external>
      {fact.value}
    </TextLink>
  );
}

function holdingsLead(listing: OpenDataListing): string {
  const formats = "Each table comes as JSON Lines and as a CSV view, with every field typed and described in datapackage.json";
  return listing.latest ? `${formats}. The links download this release's files.` : `${formats}.`;
}

export function OpenDataView({ listing }: { listing: OpenDataListing }) {
  const facts = glanceFacts(listing).map((fact) => ({ label: fact.label, value: factValue(fact) }));
  return (
    <div className="grid min-w-0 gap-12 pb-section pt-6" data-testid="open-data">
      <div className="grid min-w-0 gap-8 lg:grid-cols-12 lg:gap-10">
        <header className="grid content-start gap-3 lg:col-span-7">
          <p className="kicker">{OPEN_DATA_KICKER}</p>
          <h1 className="font-headline text-h1 text-ink-1">{listing.title}</h1>
          <p className="max-w-measure font-reading text-lede text-ink-2">{listing.summary}</p>
        </header>
        <div className="min-w-0 lg:col-span-5">
          <DatasetCitation listing={listing} />
        </div>
      </div>
      <FactGrid facts={facts} />
      <OpenDataSection id="open-data-holdings" title={HOLDINGS_TITLE} lead={holdingsLead(listing)}>
        <TableHoldings holdings={tableHoldings(listing)} />
      </OpenDataSection>
      <DatasetTerms listing={listing} />
      {listing.releases.length > 0 ? (
        <OpenDataSection id="open-data-releases" title={HISTORY_TITLE} lead="Every release keeps its own DOI and stays downloadable; CHANGES.md in each names the rows that changed.">
          <ReleaseHistory releases={listing.releases} />
        </OpenDataSection>
      ) : null}
      {listing.craftReleases.length > 0 ? <CraftReleases releases={listing.craftReleases} /> : null}
    </div>
  );
}
