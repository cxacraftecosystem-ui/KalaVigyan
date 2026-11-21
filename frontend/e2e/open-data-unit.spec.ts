import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { InstitutionFooter } from "@/components/landing/Footer";
import { PartnersFooter } from "@/components/landing/PartnersFooter";
import { OpenDataView } from "@/components/openData/OpenDataView";
import { OPEN_DATA_PATH, parseOpenDataListing, type OpenDataListing } from "@/lib/openDataContract";
import { changeLine, glanceFacts, licenceLabel, releaseRows, tableHoldings } from "@/lib/openDataView";
import { isReadingRoute } from "@/lib/readingRoutes";
import { ShapeError } from "@/lib/shape";

import { readRepo } from "./phaseBFixture";

const GAP_WORDS = /coming soon|not built yet|no data|nothing here yet|0 results|not yet|yet to be/i;

function raw(): Record<string, unknown> {
  return JSON.parse(readRepo("shared", "open-data.golden.json")) as Record<string, unknown>;
}

function listing(): OpenDataListing {
  return parseOpenDataListing(raw());
}

function beforeFirstRelease(): OpenDataListing {
  return { ...listing(), latest: null, releases: [], conceptDoi: null, conceptDoiUrl: null, citation: "KalaVigyan open knowledge [Data set]. https://kalavigyan.example/data" };
}

test("the listing parses exactly as the backend writes it and refuses a field it does not know", () => {
  expect(OPEN_DATA_PATH).toBe("/open-data");
  expect(listing() as unknown).toEqual(raw());
  expect(() => parseOpenDataListing({ ...raw(), quotes: [] })).toThrow(ShapeError);
  expect(() => parseOpenDataListing({ ...raw(), tables: [] })).toThrow(ShapeError);
});

test("at a glance names the licence, both DOIs, the counts and the size of the newest release", () => {
  expect(licenceLabel("CC-BY-4.0")).toBe("CC BY 4.0");
  expect(glanceFacts(listing()).map((fact) => [fact.label, fact.value])).toEqual([
    ["Licence", "CC BY 4.0"],
    ["This version", "2026.11.21 · 21 Nov 2026"],
    ["DOI of this version", "10.5281/zenodo.300"],
    ["DOI of every version", "10.5281/zenodo.299"],
    ["Facts", "12,345"],
    ["Sources", "0"],
    ["Crafts", "0"],
    ["Size", "1.2 MB in 2 files"]
  ]);
  expect(glanceFacts(beforeFirstRelease()).map((fact) => fact.label)).toEqual(["Licence", "Tables", "Formats", "Built by"]);
});

test("each release reads its version, day, size and what changed in its facts, the oldest as the first", () => {
  const rows = releaseRows(listing().releases);
  expect(rows.map((row) => [row.version, row.released, row.size, row.facts, row.changes])).toEqual([
    ["2026.11.21", "21 Nov 2026", "1.2 MB", "12,345", "3 facts added, 1 removed, 2 changed"],
    ["2026.10.01", "01 Oct 2026", "900 B", "12,343", "First release"]
  ]);
  expect(changeLine({ ...listing().releases[0], changes: {} }, false)).toBe("Facts unchanged");
});

test("each table lists its rows and the newest release's download links for its files", () => {
  const [families] = tableHoldings(listing());
  expect(families.rows).toBe("1 row");
  expect(families.files).toEqual([]);
  const claims = tableHoldings({ ...listing(), tables: [{ ...listing().tables[0], name: "claims", files: ["claims.jsonl", "claims.csv"] }] })[0];
  expect(claims.rows).toBe("12,345 rows");
  expect(claims.files.map((file) => file.downloadUrl)).toEqual([
    "https://zenodo.org/records/300/files/claims.jsonl?download=1",
    "https://zenodo.org/records/300/files/claims.csv?download=1"
  ]);
});

test("the page shows the dataset, its citation, its terms and its releases without a gap admission", () => {
  const markup = renderToStaticMarkup(createElement(OpenDataView, { listing: listing() }));
  expect(markup).toContain("<h1");
  expect(markup.match(/<h1/g)).toHaveLength(1);
  expect(markup).toContain("Cite this dataset");
  expect(markup).toContain("https://doi.org/10.5281/zenodo.299");
  expect(markup).toContain('data-testid="open-data-releases"');
  expect(markup).toContain("Show the 2 fields");
  expect(markup.replace(/<[^>]+>/g, " ")).not.toMatch(GAP_WORDS);
  const early = renderToStaticMarkup(createElement(OpenDataView, { listing: beforeFirstRelease() }));
  expect(early).not.toContain('data-testid="open-data-releases"');
  expect(early).toContain("https://kalavigyan.example/data");
  expect(early.replace(/<[^>]+>/g, " ")).not.toMatch(GAP_WORDS);
});

test("both footers link the dataset page, which anyone reads without signing in", () => {
  for (const markup of [renderToStaticMarkup(createElement(InstitutionFooter)), renderToStaticMarkup(createElement(PartnersFooter))]) {
    expect(markup).toContain('href="/data"');
    expect(markup).toContain("Cite this dataset");
  }
  expect(isReadingRoute("/data")).toBe(true);
});
