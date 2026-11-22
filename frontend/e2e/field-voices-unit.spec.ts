import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { checkedCraftPage } from "@/lib/craftPageChecks";
import { craftPageShape } from "@/lib/craftPageContract";
import { fieldTranscriptShape, fieldVoicesListShape, pageFieldPhotoShape, pageVoiceShape, FIELD_VOICES_PATH } from "@/lib/fieldVoicesContract";
import { parseShape, ShapeError } from "@/lib/shape";

const ROOT = join(__dirname, "..", "..");
const SOURCE = "1fc8e36a-6642-43d5-b4cd-ca1e3e532438";
const RECORDING = "b54cab0c-b7da-47d8-9da9-d9ef38d657c8";

const VOICE = {
  itemId: "FIELD_REPOSITORY:fr-media-1:fr-turn-2",
  origin: "FIELD_REPOSITORY",
  speaker: { name: "Asha Demo", line: "Asha Demo", role: "ARTISAN", yearsInCraft: 31, district: "Kachchh", state: "Gujarat" },
  quote: "અમે ફટકડીને આમલીના બીજ સાથે વાટીએ છીએ.",
  language: "gu",
  english: "We grind the alum with tamarind seed.",
  englishSource: "MACHINE",
  sourceId: SOURCE,
  locator: "0:06–0:33",
  workshop: "Ajrakh documentation visit",
  recordedOn: "2026-03-14",
  corroboratedBy: [],
  stage: { kind: "QUESTION", key: "C-Q03", label: "How do you prepare the mordant paste?" },
  citation: "Asha Demo, interview recorded 14 March 2026, Ajrakh documentation visit, Field Repository, 0:06–0:33",
  recordingId: RECORDING
};

const PHOTO = {
  itemId: "FIELD_REPOSITORY:fr-img-1",
  origin: "FIELD_REPOSITORY",
  imageUrl: "https://api.kalavigyan.example.org/api/field-voices/images/0b8a7f5e-3d1c-4f8e-9a2b-6c5d4e3f2a1b",
  width: 2400,
  height: 1600,
  caption: "Printing the first resist",
  alt: "Photograph of Ajrakh Print of Kutch: Printing the first resist",
  credit: "Asha Demo · Ajrakh documentation visit, 14 March 2026 · Field Repository",
  credited: ["Asha Demo"],
  workshop: "Ajrakh documentation visit",
  takenOn: "2026-03-14",
  groups: [{ kind: "PROCESS_STEP", key: "step:fr-step-2", label: "Ajrakh printing · First resist printing" }],
  statement: "Shown on KalaVigyan with the consent of the people pictured. Not openly licensed: ask the rights holder before any other use.",
  rightsHolder: "Field Repository",
  licence: null
};

const TESTIMONY = {
  ...VOICE,
  itemId: "kalavigyan:6d1f0f4e-2b7a-4c55-9e1d-0a1b2c3d4e5f",
  origin: "KALAVIGYAN",
  speaker: { name: null, line: "An artisan of Ajrakh Print of Kutch, Kachchh, Gujarat", role: "ARTISAN", yearsInCraft: null, district: "Kachchh", state: "Gujarat" },
  englishSource: "REVIEWED",
  workshop: null,
  recordedOn: "2026-10",
  stage: null,
  recordingId: null
};

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
