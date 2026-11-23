import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { checkedCraftPage } from "@/lib/craftPageChecks";
import { craftPageShape } from "@/lib/craftPageContract";
import { fieldTranscriptShape, fieldVoicesListShape, pageFieldPhotoShape, pageVoiceShape, FIELD_VOICES_PATH } from "@/lib/fieldVoicesContract";
import { parseShape, ShapeError } from "@/lib/shape";

import { PHOTO, RECORDING, SOURCE, TESTIMONY, VOICE } from "./fieldVoicesFixture";

const ROOT = join(__dirname, "..", "..");

function golden(name: string): Record<string, unknown> {
  return JSON.parse(readFileSync(join(ROOT, "shared", name), "utf8")) as Record<string, unknown>;
}

test("a portal quote and a KalaVigyan testimony both parse as page voices", () => {
  expect(parseShape(pageVoiceShape, VOICE)).toEqual(VOICE);
  expect(parseShape(pageVoiceShape, TESTIMONY)).toEqual(TESTIMONY);
  expect(() => parseShape(pageVoiceShape, { ...VOICE, englishSource: null })).toThrow(ShapeError);
  expect(() => parseShape(pageVoiceShape, { ...VOICE, quote: "x".repeat(601) })).toThrow(ShapeError);
  expect(() => parseShape(pageVoiceShape, { ...VOICE, village: "Ajrakhpur" })).toThrow(ShapeError);
});

test("a field photograph is credited and never openly licensed", () => {
  expect(parseShape(pageFieldPhotoShape, PHOTO)).toEqual(PHOTO);
  expect(() => parseShape(pageFieldPhotoShape, { ...PHOTO, licence: "CC BY 4.0" })).toThrow(ShapeError);
  expect(() => parseShape(pageFieldPhotoShape, { ...PHOTO, groups: [] })).toThrow(ShapeError);
});

test("the craft page lists each quote's source and counts what it shows", () => {
  const page = golden("craft.page.register.golden.json");
  expect(page.voices).toEqual([]);
  expect(page.fieldPhotos).toEqual([]);
  expect(page.fieldVoicesTotal).toEqual({ quotes: 0, images: 0 });
  const unlisted = { ...page, voices: [VOICE], fieldVoicesTotal: { quotes: 1, images: 0 } };
  expect(() => checkedCraftPage(parseShape(craftPageShape, unlisted))).toThrow(ShapeError);
  const uncounted = { ...page, fieldPhotos: [PHOTO] };
  expect(() => checkedCraftPage(parseShape(craftPageShape, uncounted))).toThrow(ShapeError);
});

test("a list page holds one kind and the transcript names only its speakers", () => {
  const list = { schemaVersion: 1, craft: { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" }, kind: "quotes", total: 2, cursor: null, nextCursor: null, quotes: [VOICE, TESTIMONY], images: [] };
  expect(parseShape(fieldVoicesListShape, list).quotes).toHaveLength(2);
  expect(() => parseShape(fieldVoicesListShape, { ...list, images: [PHOTO] })).toThrow(ShapeError);
  const line = { id: "fr-turn-2", position: 1, speakerKey: "speaker_0", locator: "0:06–0:33", language: "gu", text: VOICE.quote, english: VOICE.english, englishSource: "MACHINE", quotable: true };
  const transcript = {
    schemaVersion: 1,
    id: RECORDING,
    origin: "FIELD_REPOSITORY",
    publisher: "Field Repository",
    title: "Field interview, Ajrakh documentation visit, 14 March 2026",
    mediaType: "AUDIO",
    recordedAt: "2026-03-14T10:22:00+05:30",
    durationMs: 790000,
    crafts: [{ slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" }],
    workshop: "Ajrakh documentation visit",
    context: ["Recorded in Kachchh, Gujarat"],
    stage: null,
    speakers: [{ key: "speaker_0", label: "Asha Demo", role: "ARTISAN" }],
    lines: [line],
    english: null,
    englishSource: null,
    sourceId: SOURCE,
    citation: "Asha Demo, interview recorded 14 March 2026, Ajrakh documentation visit, Field Repository, whole recording"
  };
  expect(parseShape(fieldTranscriptShape, transcript).lines).toHaveLength(1);
  expect(() => parseShape(fieldTranscriptShape, { ...transcript, lines: [{ ...line, speakerKey: "speaker_9" }] })).toThrow(ShapeError);
  expect(FIELD_VOICES_PATH("Kutch-Ajrakh", "images", "25")).toBe("/crafts/Kutch-Ajrakh/field-voices?kind=images&cursor=25");
});
