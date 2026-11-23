import { expect, test } from "@playwright/test";

import { codeRanges, faceFor, facesDrawn, latinFaces } from "./latinFaces";

test("a monograph's and the landing's first screen find every Latin face they draw in the first request round", () => {
  const preloaded = latinFaces().filter((face) => face.preloaded);
  expect(preloaded.map((face) => face.name)).toEqual(["newsreader", "newsreaderItalic", "plexSans", "plexSansWeights"]);
  expect(preloaded.flatMap((face) => face.files)).toEqual(["newsreader-latin-var.woff2", "newsreader-italic-latin-var.woff2", "ibm-plex-sans-regular-latin1.woff2", "ibm-plex-sans-medium-latin1.woff2", "ibm-plex-sans-semibold-latin1.woff2"]);
});

test("the extended ranges, symbols and code faces still load only when a page draws them", () => {
  const deferred = latinFaces().filter((face) => !face.preloaded);
  expect(deferred.map((face) => face.name)).toEqual(["newsreaderExtended", "newsreaderArrows", "plexSansItalic", "plexSansLatin2", "plexSansLatin3", "plexSansSymbols", "plexMono"]);
});

test("a drawn character is matched to the face whose family, style, nearest weight and range cover it", () => {
  const faces = latinFaces();
  expect(codeRanges("U+0000-00FF, U+0131")).toEqual([
    [0, 255],
    [305, 305]
  ]);
  const roman = { family: "Newsreader", style: "normal", weight: 470 };
  expect(faceFor(faces, roman, "K".codePointAt(0) ?? 0)?.name).toBe("newsreader");
  expect(faceFor(faces, roman, "ā".codePointAt(0) ?? 0)?.name).toBe("newsreaderExtended");
  expect(faceFor(faces, roman, "→".codePointAt(0) ?? 0)?.name).toBe("newsreaderArrows");
  expect(faceFor(faces, { ...roman, style: "italic", weight: 400 }, "a".codePointAt(0) ?? 0)?.name).toBe("newsreaderItalic");
  expect(faceFor(faces, { family: "IBM Plex Sans", style: "normal", weight: 600 }, "A".codePointAt(0) ?? 0)?.name).toBe("plexSansWeights");
  expect(faceFor(faces, { family: "IBM Plex Sans", style: "normal", weight: 300 }, "A".codePointAt(0) ?? 0)?.name).toBe("plexSans");
  expect(faceFor(faces, { family: "Georgia", style: "normal", weight: 400 }, "A".codePointAt(0) ?? 0)).toBeNull();
  const texts = [
    { family: "IBM Plex Sans", style: "normal", weight: 500, text: "Listen" },
    { family: "Newsreader", style: "italic", weight: 400, text: "Two artisans" }
  ];
  expect([...facesDrawn(faces, texts)].sort()).toEqual(["newsreaderItalic", "plexSansWeights"]);
});
