import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CiteThis } from "@/components/craft/CiteThis";
import { CRAFT_RELEASES_TITLE } from "@/components/openData/CraftReleases";
import { CraftReleaseLine } from "@/components/openData/CraftReleaseLine";
import { OpenDataView } from "@/components/openData/OpenDataView";
import { sharedOpenData } from "@/lib/openData";
import { parseOpenDataListing, type CraftRelease, type OpenDataListing } from "@/lib/openDataContract";
import { craftOfPage, craftReleaseFor, craftReleaseRows } from "@/lib/openDataCrafts";
import { ShapeError } from "@/lib/shape";

import { readRepo } from "./phaseBFixture";

const GAP_WORDS = /coming soon|not built yet|no data|nothing here yet|0 results|not yet|yet to be/i;
const AJRAKH_PAGE = "https://kalavigyan.vercel.app/crafts/kutch-ajrakh/v3";

function raw(): Record<string, unknown> {
  return JSON.parse(readRepo("shared", "open-data.golden.json")) as Record<string, unknown>;
}

function listing(): OpenDataListing {
  return parseOpenDataListing(raw());
}

function ajrakh(): CraftRelease {
  return listing().craftReleases[0];
}

test("a craft release parses with its craft, its name and both DOIs, and refuses one without its craft", () => {
  expect(ajrakh().craft).toBe("Kutch-Ajrakh");
  expect([ajrakh().craftName, ajrakh().title]).toEqual(["Kutch Ajrakh", "Kutch Ajrakh: KalaVigyan open knowledge"]);
  expect([ajrakh().doiUrl, ajrakh().conceptDoiUrl]).toEqual(["https://doi.org/10.5281/zenodo.400", "https://doi.org/10.5281/zenodo.399"]);
  const [first] = raw().craftReleases as Record<string, unknown>[];
  const { craft: _craft, ...unnamed } = first;
  expect(_craft).toBe("Kutch-Ajrakh");
  expect(() => parseOpenDataListing({ ...raw(), craftReleases: [unnamed] })).toThrow(ShapeError);
  expect(() => parseOpenDataListing({ ...raw(), craftReleases: [{ ...first, quotes: [] }] })).toThrow(ShapeError);
});

test("each craft release reads its craft, the page it links, its day, its facts and its size", () => {
  expect(craftReleaseRows(listing().craftReleases)).toEqual([
    {
      key: "Kutch-Ajrakh-2026.11.22",
      craft: "Kutch Ajrakh",
      craftHref: "/crafts/Kutch-Ajrakh",
      version: "2026.11.22",
      released: "22 Nov 2026",
      doi: "10.5281/zenodo.400",
      doiUrl: "https://doi.org/10.5281/zenodo.400",
      conceptDoi: "10.5281/zenodo.399",
      conceptDoiUrl: "https://doi.org/10.5281/zenodo.399",
      facts: "321",
      size: "64.0 KB"
    }
  ]);
});

test("a craft page finds its own newest release by its address and any other page finds none", () => {
  expect(craftOfPage(AJRAKH_PAGE)).toBe("kutch-ajrakh");
  expect(craftOfPage("https://kalavigyan.vercel.app/crafts/Kutch-Ajrakh")).toBe("kutch-ajrakh");
  expect(craftOfPage("https://kalavigyan.vercel.app/answers/abc")).toBeNull();
  expect(craftReleaseFor(listing(), AJRAKH_PAGE)?.doi).toBe("10.5281/zenodo.400");
  expect(craftReleaseFor(listing(), "https://kalavigyan.vercel.app/crafts/block-printing-of-akola/v1")).toBeNull();
  expect(craftReleaseFor(null, AJRAKH_PAGE)).toBeNull();
  const older = { ...ajrakh(), version: "2026.11.20", doi: "10.5281/zenodo.390", publishedAt: "2026-11-20T10:00:00Z" };
  expect(craftReleaseFor({ ...listing(), craftReleases: [older, ajrakh()] }, AJRAKH_PAGE)?.doi).toBe("10.5281/zenodo.400");
});

test("the data page lists the craft releases after every release, linking each craft and both DOIs", () => {
  const markup = renderToStaticMarkup(createElement(OpenDataView, { listing: listing() }));
  expect(markup).toContain(CRAFT_RELEASES_TITLE);
  expect(markup.indexOf('data-testid="open-data-releases"')).toBeLessThan(markup.indexOf('data-testid="open-data-craft-releases"'));
  expect(markup).toContain('href="/crafts/Kutch-Ajrakh"');
  expect(markup).toContain('href="https://doi.org/10.5281/zenodo.400"');
  expect(markup).toContain('href="https://doi.org/10.5281/zenodo.399"');
  expect(markup.replace(/<[^>]+>/g, " ")).not.toMatch(GAP_WORDS);
  const none = renderToStaticMarkup(createElement(OpenDataView, { listing: { ...listing(), craftReleases: [] } }));
  expect(none).not.toContain('data-testid="open-data-craft-releases"');
  expect(none).not.toContain(CRAFT_RELEASES_TITLE);
});

test("the DOI line names the release's version and opens its DOI, and a monograph shows nothing new before it", () => {
  const line = renderToStaticMarkup(createElement(CraftReleaseLine, { release: ajrakh() }));
  expect(line).toContain("Its open data, version 2026.11.22");
  expect(line).toContain('href="https://doi.org/10.5281/zenodo.400"');
  expect(line).toContain('target="_blank"');
  const cite = { kind: "monograph" as const, title: "Kutch Ajrakh", version: 3, url: AJRAKH_PAGE, key: "kalavigyan_kutch_ajrakh_v3" };
  const monograph = renderToStaticMarkup(createElement(CiteThis, { cite }));
  expect(monograph).toContain("Cite this monograph");
  expect(monograph).not.toContain('data-testid="craft-release-doi"');
});

test("the listing is read once for every craft page and read again after a failure", async () => {
  let calls = 0;
  const failing = async (): Promise<OpenDataListing> => {
    calls += 1;
    throw new Error("unreachable");
  };
  expect(await sharedOpenData(failing)).toBeNull();
  const reading = async (): Promise<OpenDataListing> => {
    calls += 1;
    return listing();
  };
  expect((await sharedOpenData(reading))?.craftReleases).toHaveLength(1);
  expect((await sharedOpenData(reading))?.craftReleases).toHaveLength(1);
  expect(calls).toBe(2);
});
