"use client";

import { useId, useState } from "react";

import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { TextLink } from "@/components/ui/TextLink";
import { CITE_STYLES, type CiteStyle } from "@/lib/monographCite";
import type { OpenDataListing } from "@/lib/openDataContract";

export const CITE_DATASET = "Cite this dataset";
const COPIED = "Citation copied.";
const NOT_COPIED = "The citation could not be copied. Select the text and copy it.";

function Addresses({ listing }: { listing: OpenDataListing }) {
  const latest = listing.latest;
  if (!latest) {
    return (
      <p className="kv-citethis-url">
        <TextLink href={listing.pageUrl}>{listing.pageUrl}</TextLink>
      </p>
    );
  }
  return (
    <dl className="grid gap-1 font-ui text-label text-ink-3">
      <div className="flex flex-wrap gap-x-2">
        <dt>This version</dt>
        <dd className="kv-citethis-url">
          <TextLink href={latest.doiUrl} external>
            {latest.doiUrl}
          </TextLink>
        </dd>
      </div>
      {listing.conceptDoiUrl ? (
        <div className="flex flex-wrap gap-x-2">
          <dt>Every version</dt>
          <dd className="kv-citethis-url">
            <TextLink href={listing.conceptDoiUrl} external>
              {listing.conceptDoiUrl}
            </TextLink>
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

export function DatasetCitation({ listing }: { listing: OpenDataListing }) {
  const [style, setStyle] = useState<CiteStyle>("text");
  const [status, setStatus] = useState("");
  const headingId = useId();
  const shown = style === "bibtex" ? listing.bibtex : listing.citation;

  async function copy() {
    try {
      await navigator.clipboard.writeText(shown);
      setStatus(COPIED);
    } catch {
      setStatus(NOT_COPIED);
    }
  }

  return (
    <section className="kv-citethis" aria-labelledby={headingId} data-testid="cite-dataset">
      <h2 id={headingId} className="font-reading text-h3 text-ink-1">
        {CITE_DATASET}
      </h2>
      <SegmentedChoice label="Citation style" value={style} options={CITE_STYLES.map((option) => ({ ...option }))} onChange={(value) => setStyle(value as CiteStyle)} />
      <pre className="kv-citethis-text" data-style={style}>
        {shown}
      </pre>
      <Addresses listing={listing} />
      <p className="font-reading text-body-sm text-ink-2">{listing.attribution}</p>
      <ActionGroup align="start">
        <Button variant="quiet" size="sm" onClick={copy}>
          Copy citation
        </Button>
      </ActionGroup>
      <p className="kv-citethis-status" role="status">
        {status}
      </p>
    </section>
  );
}
