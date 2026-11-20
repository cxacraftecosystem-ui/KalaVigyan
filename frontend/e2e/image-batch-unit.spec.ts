import { expect, test } from "@playwright/test";

import { batchBody, batchProblems, BATCH_PICTURES_MAX, type ImageBatchInput } from "../lib/imageBatch";

const VAT = { caption: " The vat at dawn ", altText: "A clay vat with a blue film", prompt: " An indigo vat at dawn " };
const AI_BATCH: ImageBatchInput = {
  craftSlug: "Kutch-Ajrakh",
  origin: "AI_GENERATED",
  generator: " ChatGPT, gpt-image-1 ",
  claimIds: ["4d1c2b3a-0000-4000-8000-000000000001"],
  pictures: [
    VAT,
    { caption: "Printing the resist", altText: "A carved block on red cloth", prompt: "A block being printed" }
  ]
};

const file = (name: string, type = "image/png", size = 2_000) => ({ name, type, size }) as File;

test("several pictures share one declaration and each keeps its own words", () => {
  expect(batchBody(AI_BATCH)).toEqual({
    craftSlug: "Kutch-Ajrakh",
    origin: "AI_GENERATED",
    generator: "ChatGPT, gpt-image-1",
    rightsConfirmed: true,
    termsVersion: "2026-11-19",
    pictures: [
      {
        claimIds: ["4d1c2b3a-0000-4000-8000-000000000001"],
        prompt: "An indigo vat at dawn",
        caption: "The vat at dawn",
        altText: "A clay vat with a blue film"
      },
      {
        claimIds: ["4d1c2b3a-0000-4000-8000-000000000001"],
        prompt: "A block being printed",
        caption: "Printing the resist",
        altText: "A carved block on red cloth"
      }
    ]
  });
});

test("a photograph batch sends no tool or prompt", () => {
  const photos = batchBody({ ...AI_BATCH, origin: "PHOTOGRAPH" });
  expect(photos).toMatchObject({ origin: "PHOTOGRAPH", generator: null });
  expect((photos.pictures as Array<Record<string, unknown>>).map((picture) => picture.prompt)).toEqual([null, null]);
});

test("each picture of a batch names its own problems by its number", () => {
  const missing = { ...AI_BATCH, pictures: [VAT, { caption: "", altText: "x", prompt: "" }] };
  expect(batchProblems(missing, [file("a.png"), file("b.pdf", "application/pdf")])).toEqual([
    "Picture 2: Write a caption.",
    "Picture 2: Describe the picture for readers who cannot see it.",
    "Picture 2: Give the prompt.",
    "Picture 2: Choose a PNG, JPEG, WebP, AVIF, GIF, HEIC, TIFF, BMP or SVG picture."
  ]);
  expect(batchProblems(AI_BATCH, [file("a.png"), file("b.heic", "image/heic")])).toEqual([]);
  expect(BATCH_PICTURES_MAX).toBe(10);
});
