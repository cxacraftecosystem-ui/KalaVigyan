import { expect, test } from "@playwright/test";

import { clusterName, shownNumbers } from "@/lib/citationCluster";
import type { MonographDocument } from "@/lib/monographDocument";
import { namedCitations, withNamedCitations, withNamedStrings } from "@/lib/monographRenderCitations";

const OLD_PAIR =
  '<span class="nw">dyes<button class="kcite" type="button" data-c="pt:C1" data-g="g3 g1" aria-haspopup="dialog" aria-expanded="false" aria-label="Sources 1 and 3" aria-description="GI Journal; Khatris">1,3</button></span>';
const NEW_PAIR =
  '<span class="nw">dyes<button class="kcite" type="button" data-c="pt:C1" data-g="g3 g1" aria-haspopup="dialog" aria-expanded="false" aria-label="Sources 1, 3" aria-description="GI Journal; Khatris">1,3</button></span>';

function words(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .split(" ")
    .filter(Boolean);
}

function holdsRun(name: string, shown: string): boolean {
  const haystack = words(name);
  const needle = words(shown);
  return haystack.some((_, start) => needle.every((word, at) => haystack[start + at] === word));
}

test("a citation's accessible name holds its shown numerals as one unbroken run, as WCAG 2.5.3 asks", () => {
  expect(clusterName([{ number: 4 }])).toBe("Source 4");
  expect(clusterName([{ number: 1 }, { number: 4 }, { number: 5 }])).toBe("Sources 1, 4, 5");
  expect(clusterName([{ number: 2 }, { number: null }, { number: null }])).toBe("Sources 2 and 2 more");
  for (const shown of ["7", "1,4,5", "12,30", "2,·,·"]) expect(holdsRun(clusterName(shownNumbers(shown)), shown), shown).toBe(true);
});

test("the shown numerals of a cluster read back as its entries, a dot standing for an unnumbered source", () => {
  expect(shownNumbers("1,14")).toEqual([{ number: 1 }, { number: 14 }]);
  expect(shownNumbers("5,·")).toEqual([{ number: 5 }, { number: null }]);
});

test("a citation button written into a fragment or a data string is renamed from its own numerals and nothing else changes", () => {
  expect(namedCitations(OLD_PAIR)).toBe(NEW_PAIR);
  expect(namedCitations(`<p>${OLD_PAIR} and ${OLD_PAIR}</p>`)).toBe(`<p>${NEW_PAIR} and ${NEW_PAIR}</p>`);
  expect(namedCitations("<p>No citation here.</p>")).toBe("<p>No citation here.</p>");
  expect(withNamedStrings({ quiz: [{ cite: OLD_PAIR, n: 3 }], open: null })).toEqual({ quiz: [{ cite: NEW_PAIR, n: 3 }], open: null });
});

test("a document's shell, fragments, specs and data are renamed, and its units are left to the renderer", () => {
  const unit = { chapter: "c", tag: "p", field: null, nodes: ["x"], claimIds: [] };
  const document = {
    shell: `<main id="kv-main">${OLD_PAIR}</main>`,
    fragments: { "a/b/c": OLD_PAIR },
    specs: { "a/b/c": { held: OLD_PAIR } },
    content: { data: { "cite-data": [OLD_PAIR] }, units: { u1: unit } }
  } as unknown as MonographDocument;
  const named = withNamedCitations(document);
  expect(named.shell).toBe(`<main id="kv-main">${NEW_PAIR}</main>`);
  expect(named.fragments).toEqual({ "a/b/c": NEW_PAIR });
  expect(named.specs).toEqual({ "a/b/c": { held: NEW_PAIR } });
  expect(named.content.data).toEqual({ "cite-data": [NEW_PAIR] });
  expect(named.content.units).toBe(document.content.units);
});
