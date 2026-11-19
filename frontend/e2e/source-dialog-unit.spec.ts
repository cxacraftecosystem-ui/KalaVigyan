import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { openedSource, SourceDetails } from "@/components/answer/SourceDialog";
import { citationsBySource } from "@/lib/citations";
import type { Citation, SourceRef } from "@/lib/types";

const SOURCE: SourceRef = {
  id: "s-gi",
  kind: "GOVERNMENT",
  title: "Geographical Indications Journal No. 188",
  authors: [],
  year: 2023,
  doi: null,
  url: "https://search.ipindia.gov.in/GIRPublicSearch/",
  publisher: "Intellectual Property India",
  licence: null,
  attribution: null,
  reliability: "A"
};

const passage = (claimId: string, quote: string | null, locator: string | null): Citation => ({
  id: `${claimId}:${SOURCE.id}`,
  claimId,
  sourceId: SOURCE.id,
  quote,
  locator,
  context: null,
  evidence: quote === null ? "INFERRED" : "QUOTED",
  level: "PROVISIONAL"
});

const QUOTES = [passage("k1", "printed on both sides of the cloth", "p. 14"), passage("k2", "washed in the river Saran", "p. 15")];

function blocks(html: string): string[] {
  return html.split('data-testid="source-quote"').slice(1);
}

test("a source cited twice in one sentence opens with both passages, each with its locator", () => {
  const [cluster] = citationsBySource(QUOTES, new Map([[SOURCE.id, 3]]));
  const opened = openedSource(cluster.citations, new Map([[SOURCE.id, 3]]), new Map([[SOURCE.id, SOURCE]]));
  const html = renderToStaticMarkup(createElement(SourceDetails, { open: opened }));
  const found = blocks(html);
  expect(found).toHaveLength(2);
  expect(found[0]).toContain("printed on both sides of the cloth");
  expect(found[0]).toContain("p. 14");
  expect(found[1]).toContain("washed in the river Saran");
  expect(found[1]).toContain("p. 15");
  expect(html).toContain(">Source 3<");
});

test("a passage without a quote still shows its locator and says it was inferred", () => {
  const opened = openedSource([passage("k3", null, "Table 2")], new Map(), new Map([[SOURCE.id, SOURCE]]));
  const [only] = blocks(renderToStaticMarkup(createElement(SourceDetails, { open: opened })));
  expect(only).toContain("Table 2");
  expect(only).toContain("no passage is quoted");
});
