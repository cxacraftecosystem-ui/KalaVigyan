"use client";

import { useEffect, useId, useState } from "react";

import { CraftReleaseDoi } from "@/components/openData/CraftReleaseDoi";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { CITE_STYLES, citation, type Citable, type CiteStyle } from "@/lib/monographCite";

export const CITE_HEADINGS = { monograph: "Cite this monograph", answer: "Cite this answer" } as const;
const COPIED = "Citation copied.";
const NOT_COPIED = "The citation could not be copied. Select the text and copy it.";

export function CiteThis({ cite }: { cite: Citable }) {
  const [style, setStyle] = useState<CiteStyle>("text");
  const [accessed, setAccessed] = useState<Date | null>(null);
  const [status, setStatus] = useState("");
  const headingId = useId();
  useEffect(() => setAccessed(new Date()), []);
  const shown = citation(cite, style, accessed);

  async function copy() {
    const today = new Date();
    setAccessed(today);
    try {
      await navigator.clipboard.writeText(citation(cite, style, today));
      setStatus(COPIED);
    } catch {
      setStatus(NOT_COPIED);
    }
  }

  return (
    <section className="kv-citethis" aria-labelledby={headingId} data-testid="cite-this">
      <h2 id={headingId} className="font-reading text-h3 text-ink-1">
        {CITE_HEADINGS[cite.kind]}
      </h2>
      <SegmentedChoice label="Citation style" value={style} options={CITE_STYLES.map((option) => ({ ...option }))} onChange={(value) => setStyle(value as CiteStyle)} />
      <pre className="kv-citethis-text" data-style={style}>
        {shown}
      </pre>
      <p className="kv-citethis-url">
        <a href={cite.url}>{cite.url}</a>
      </p>
      {cite.kind === "monograph" ? <CraftReleaseDoi pageUrl={cite.url} /> : null}
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
