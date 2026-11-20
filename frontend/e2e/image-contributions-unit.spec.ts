import { expect, test } from "@playwright/test";

import {
  canWithdraw,
  declarationBody,
  declarationProblems,
  fileProblem,
  heldReasons,
  IMAGE_TERMS_VERSION,
  imageContributionShape,
  previewable,
  sentNotice,
  shownCredit,
  type ImageContribution,
  type ImageDeclaration
} from "../lib/imageContributionContract";
import { ROUTE_GUARDS } from "../lib/permissions";
import { parseShape } from "../lib/shape";

const PHOTO: ImageDeclaration = {
  craftSlug: "Kutch-Ajrakh",
  stageId: null,
  claimIds: [],
  origin: "PHOTOGRAPH",
  generator: "left over from an earlier choice",
  prompt: "left over",
  caption: "A printer lifts the block",
  altText: "Hands lifting a carved wooden block from red cloth"
};

const VIEW: ImageContribution = {
  id: "8b2f1d8e-2c1b-4c55-9a33-6a7b1c2d3e4f",
  craftSlug: "Kutch-Ajrakh",
  craftName: "Kutch Ajrakh",
  stageId: null,
  materialId: null,
  slot: "MASTHEAD",
  taskKey: "MISSING_PICTURE:craft:Kutch-Ajrakh:slot-masthead",
  claimIds: ["4d1c2b3a-0000-4000-8000-000000000001"],
  origin: "AI_GENERATED",
  label: "Illustration, made with ChatGPT, gpt-image-1",
  generator: "ChatGPT, gpt-image-1",
  prompt: "An indigo vat",
  caption: "The vat turns yellow-green",
  altText: "A clay vat",
  status: "PENDING",
  aiMarked: true,
  mime: "image/png",
  width: 800,
  height: 600,
  fileUrl: "https://bucket.example/media/x.png",
  screen: { verdict: "CLEAR", flags: [], reasons: [] },
  createdAt: "2026-11-19T10:00:00Z",
  reviewedAt: null,
  reviewNote: null
};

test("an AI-made picture names its tool, its prompt and the facts it shows", () => {
  const ai = { ...PHOTO, origin: "AI_GENERATED" as const, generator: " ", prompt: "", claimIds: [] };
  expect(declarationProblems(ai)).toEqual(["Name the AI tool and model.", "Give the prompt.", "Choose the facts the picture shows."]);
  expect(declarationProblems({ ...ai, generator: "ChatGPT", prompt: "A vat", claimIds: ["c1"] })).toEqual([]);
});

test("a photograph needs a craft, a caption and a description, and sends no tool or prompt", () => {
  expect(declarationProblems({ ...PHOTO, craftSlug: "", caption: "  ", altText: "x" })).toEqual([
    "Choose the craft it shows.",
    "Write a caption.",
    "Describe the picture for readers who cannot see it."
  ]);
  expect(declarationBody(PHOTO)).toEqual({
    craftSlug: "Kutch-Ajrakh",
    stageId: null,
    claimIds: [],
    origin: "PHOTOGRAPH",
    generator: null,
    prompt: null,
    caption: "A printer lifts the block",
    altText: "Hands lifting a carved wooden block from red cloth",
    rightsConfirmed: true,
    termsVersion: IMAGE_TERMS_VERSION
  });
});

test("pictures in every accepted format of 10 MB or less are sent, a HEIC known by its name too", () => {
  const picture = (type: string, size: number, name = "picture") => ({ type, size, name });
  expect(fileProblem(picture("image/png", 2_000_000))).toBeNull();
  expect(fileProblem(picture("image/gif", 2_000))).toBeNull();
  expect(fileProblem(picture("image/svg+xml", 2_000))).toBeNull();
  expect(fileProblem(picture("", 3_000_000, "IMG_0042.HEIC"))).toBeNull();
  expect(fileProblem(picture("application/pdf", 2_000, "notes.pdf"))).toBe("Choose a PNG, JPEG, WebP, AVIF, GIF, HEIC, TIFF, BMP or SVG picture.");
  expect(fileProblem(picture("image/jpeg", 11 * 1024 * 1024))).toBe("Choose a picture of 10 MB or less.");
});

test("a browser draws the chosen picture before it is sent unless it is converted on arrival", () => {
  expect(previewable({ type: "image/avif" })).toBe(true);
  expect(previewable({ type: "image/heic" })).toBe(false);
  expect(previewable({ type: "image/tiff" })).toBe(false);
});

test("the preview credits a photograph to KalaVigyan and an AI picture to its tool, never the contributor", () => {
  expect(shownCredit("PHOTOGRAPH", null)).toBe("Contributed to KalaVigyan");
  expect(shownCredit("AI_GENERATED", " ChatGPT, gpt-image-1 ")).toBe("Illustration, made with ChatGPT, gpt-image-1");
});

test("a picture held by the screen says why, and a clear or approved one does not", () => {
  const held = { ...VIEW, screen: { verdict: "FLAGGED" as const, flags: ["ID_DOCUMENT"], reasons: ["It may show an identity document, or a card with a face and a number."] } };
  expect(heldReasons(VIEW)).toEqual([]);
  expect(heldReasons(held)).toEqual(["It may show an identity document, or a card with a face and a number."]);
  expect(sentNotice(held)).toBe("Waiting for review: an Admin looks at it first. It may show an identity document, or a card with a face and a number.");
  expect(sentNotice(VIEW)).toBe("Waiting for review. An Admin will look at it.");
  expect(sentNotice({ ...VIEW, status: "APPROVED" })).toBe("Your picture is approved and shown.");
});

test("a picture can be taken back only while it waits, because consent cannot be revoked", () => {
  expect(canWithdraw(VIEW)).toBe(true);
  expect(canWithdraw({ ...VIEW, status: "AWAITING_FILE" })).toBe(true);
  expect(canWithdraw({ ...VIEW, status: "APPROVED" })).toBe(false);
  expect(canWithdraw({ ...VIEW, status: "REJECTED" })).toBe(false);
});

test("the server's picture view parses, and an unknown status is refused", () => {
  expect(parseShape(imageContributionShape, VIEW)).toEqual(VIEW);
  expect(() => parseShape(imageContributionShape, { ...VIEW, status: "HIDDEN" })).toThrow();
  expect(() => parseShape(imageContributionShape, { ...VIEW, slot: "COVER" })).toThrow();
  expect(parseShape(imageContributionShape, { ...VIEW, screen: null })).toEqual({ ...VIEW, screen: null });
});

test("the picture pages are guarded by the capabilities the API requires", () => {
  const gates = Object.fromEntries(ROUTE_GUARDS.map((guard) => [guard.path, guard.gate]));
  expect(gates["/contributions/pictures"]).toBe("require(PROPOSE_KNOWLEDGE)");
  expect(gates["/admin/pictures"]).toBe("require(REVIEW_CONTRIBUTIONS)");
});
