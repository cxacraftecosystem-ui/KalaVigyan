import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

const LATIN_FONTS = join(__dirname, "..", "app", "latinFonts.ts");

type Face = { name: string; files: string[]; preloaded: boolean };

function faces(source: string): Face[] {
  return source.split(/\nconst /).slice(1).filter((block) => block.includes("localFont(")).map((block) => ({
    name: block.slice(0, block.indexOf(" ")),
    files: [...block.matchAll(/\.\.\/fonts\/([a-z0-9-]+\.woff2)/g)].map((found) => found[1]),
    preloaded: !block.includes("preload: false")
  }));
}

test("a monograph's and the landing's first screen find every Latin face they draw in the first request round", () => {
  const preloaded = faces(readFileSync(LATIN_FONTS, "utf8")).filter((face) => face.preloaded);
  expect(preloaded.map((face) => face.name)).toEqual(["newsreader", "newsreaderItalic", "plexSans", "plexSansWeights", "plexSansItalic"]);
  expect(preloaded.flatMap((face) => face.files)).toEqual([
    "newsreader-latin-var.woff2",
    "newsreader-italic-latin-var.woff2",
    "ibm-plex-sans-regular-latin1.woff2",
    "ibm-plex-sans-medium-latin1.woff2",
    "ibm-plex-sans-semibold-latin1.woff2",
    "ibm-plex-sans-italic-latin1.woff2"
  ]);
});

test("the extended ranges, symbols and code faces still load only when a page draws them", () => {
  const deferred = faces(readFileSync(LATIN_FONTS, "utf8")).filter((face) => !face.preloaded);
  expect(deferred.map((face) => face.name)).toEqual(["newsreaderExtended", "newsreaderArrows", "plexSansLatin2", "plexSansLatin3", "plexSansSymbols", "plexMono"]);
});
