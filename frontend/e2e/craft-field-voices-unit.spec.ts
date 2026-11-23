import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { FieldVoicesPart } from "@/components/craft/FieldVoicesPart";
import type { FieldListKind, FieldVoicesList, PageFieldPhoto, PageVoice } from "@/lib/fieldVoicesContract";
import { photoGroups, quotesOf, restOfList, type FieldVoicesFirst } from "@/lib/fieldVoicesView";

import { PHOTO, RECORDING, TESTIMONY, VOICE } from "./fieldVoicesFixture";

const CRAFT = { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" };

function page(kind: FieldListKind, items: { quotes?: PageVoice[]; images?: PageFieldPhoto[] }, total: number, nextCursor: string | null = null): FieldVoicesList {
  return { schemaVersion: 1, craft: CRAFT, kind, total, cursor: null, nextCursor, quotes: items.quotes ?? [], images: items.images ?? [] };
}

function voices(count: number): PageVoice[] {
  return Array.from({ length: count }, (_, at) => ({ ...VOICE, itemId: `${VOICE.itemId}-${at + 1}` }));
}

function photos(count: number): PageFieldPhoto[] {
  return Array.from({ length: count }, (_, at) => ({ ...PHOTO, itemId: `${PHOTO.itemId}-${at + 1}` }));
}

function drawn(first: FieldVoicesFirst | null): string {
  return renderToStaticMarkup(createElement(FieldVoicesPart, { first }));
}

function count(html: string, testId: string): number {
  return html.split(`data-testid="${testId}"`).length - 1;
}

const NO_PHOTOS = page("images", {}, 0);
const NO_QUOTES = page("quotes", {}, 0);

test("a craft with no field voices draws nothing at all", () => {
  expect(drawn(null)).toBe("");
  expect(drawn({ quotes: NO_QUOTES, images: NO_PHOTOS })).toBe("");
});

test("the first page shows six quotes and Show all counts every quote the list holds", () => {
  const html = drawn({ quotes: page("quotes", { quotes: voices(8) }, 40, "25"), images: NO_PHOTOS });
  expect(count(html, "field-voice")).toBe(6);
  expect(html).toContain("In the artisan&#x27;s words");
  expect(html).toContain("Show all 40");
  expect(html).toContain('aria-expanded="false"');
  expect(count(html, "workshop-gallery")).toBe(0);
});

test("a short list of quotes shows them all with no Show all", () => {
  const html = drawn({ quotes: page("quotes", { quotes: voices(2) }, 2), images: NO_PHOTOS });
  expect(count(html, "field-voice")).toBe(2);
  expect(html).not.toContain("Show all");
});

test("a recorded quote links its full interview, beside its citation and its English", () => {
  const html = drawn({ quotes: page("quotes", { quotes: [VOICE, TESTIMONY] }, 2), images: NO_PHOTOS });
  expect(html.split(`href="/voices/${RECORDING}"`).length - 1).toBe(1);
  expect(html).toContain("Read the full interview");
  expect(html).toContain(VOICE.citation);
  expect(html).toContain("We grind the alum with tamarind seed.");
  expect(html).toContain("Machine translation");
  expect(html).toContain('lang="gu"');
  expect(html).toContain('data-origin="KALAVIGYAN"');
});

test("the gallery shows twelve photographs, each captioned first and credited with its rights", () => {
  const html = drawn({ quotes: NO_QUOTES, images: page("images", { images: photos(14) }, 14) });
  expect(count(html, "field-photo")).toBe(12);
  expect(html).toContain("From the workshops");
  expect(html).toContain("Show all 14");
  expect(html).toContain(`<p class="kv-caption">${PHOTO.caption}</p><p class="kv-credit">${PHOTO.credit}<span class="block">`);
  expect(html).toContain(`${PHOTO.statement} Rights holder: ${PHOTO.rightsHolder}.`);
  expect(html).toContain(`alt="${PHOTO.alt}"`);
});

test("photographs are grouped by their first placement in the order they first appear", () => {
  const step = PHOTO.groups[0];
  const product = { kind: "PRODUCT" as const, key: "product:stole", label: "Ajrakh stole" };
  const shown = [
    { ...PHOTO, itemId: "a" },
    { ...PHOTO, itemId: "b", groups: [product, step] },
    { ...PHOTO, itemId: "c" }
  ];
  const groups = photoGroups(shown);
  expect(groups.map((group) => [group.label, group.photos.map((photo) => photo.itemId)])).toEqual([
    [step.label, ["a", "c"]],
    ["Ajrakh stole", ["b"]]
  ]);
});

test("Show all reads every later page in order and refuses a list that does not move", async () => {
  const later: Record<string, FieldVoicesList> = {
    "25": page("quotes", { quotes: voices(2) }, 4, "50"),
    "50": page("quotes", { quotes: [TESTIMONY] }, 4, null)
  };
  const rest = await restOfList("25", async (cursor) => later[cursor], quotesOf);
  expect(rest.map((voice) => voice.itemId)).toEqual([`${VOICE.itemId}-1`, `${VOICE.itemId}-2`, TESTIMONY.itemId]);
  const stuck = page("quotes", { quotes: voices(1) }, 4, "25");
  await expect(restOfList("25", async () => stuck, quotesOf)).rejects.toThrow("does not move past cursor 25");
});
