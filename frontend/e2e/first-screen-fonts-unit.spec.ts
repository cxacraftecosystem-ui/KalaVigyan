import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

const APP = join(__dirname, "..", "app");

type Face = { name: string; body: string; preloaded: boolean };

function faces(file: string): Face[] {
  const source = readFileSync(join(APP, file), "utf8");
  return source.split(/\nconst /).slice(1).filter((block) => block.includes("localFont(")).map((block) => ({
    name: block.slice(0, block.indexOf(" ")),
    body: block.slice(block.indexOf("{"), block.indexOf("\n});")).replace(/\n\s*variable: "[^"]+",/, ""),
    preloaded: !block.includes("preload: false")
  }));
}

function files(face: Face): string[] {
  return [...face.body.matchAll(/\.\.\/fonts\/([a-z0-9-]+\.woff2)/g)].map((found) => found[1]);
}

test("every page preloads only the roman reading face and the regular interface face", () => {
  const preloaded = faces("latinFonts.ts").filter((face) => face.preloaded);
  expect(preloaded.flatMap(files)).toEqual(["newsreader-latin-var.woff2", "ibm-plex-sans-regular-latin1.woff2"]);
});

test("the landing preloads exactly the faces its first screen draws, declared as every page declares them", () => {
  const shared = new Map(faces("latinFonts.ts").map((face) => [face.name, face]));
  const landing = faces("landingFonts.ts");
  expect(landing.every((face) => face.preloaded)).toBe(true);
  expect(landing.flatMap(files)).toEqual(["ibm-plex-sans-medium-latin1.woff2", "ibm-plex-sans-semibold-latin1.woff2", "newsreader-italic-latin-var.woff2"]);
  expect(landing.map((face) => face.body)).toEqual([shared.get("plexSansWeights")?.body.replace("  preload: false,\n", ""), shared.get("newsreaderItalic")?.body.replace("  preload: false,\n", "")]);
  expect(readFileSync(join(APP, "page.tsx"), "utf8")).toContain('import "./landingFonts";');
});
