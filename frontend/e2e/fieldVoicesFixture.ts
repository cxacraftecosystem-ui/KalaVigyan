import type { PageFieldPhoto, PageVoice } from "@/lib/fieldVoicesContract";

export const SOURCE = "1fc8e36a-6642-43d5-b4cd-ca1e3e532438";
export const RECORDING = "b54cab0c-b7da-47d8-9da9-d9ef38d657c8";

export const VOICE: PageVoice = {
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

export const PHOTO: PageFieldPhoto = {
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

export const TESTIMONY: PageVoice = {
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
