import { expect, test } from "@playwright/test";

import { routeGuardFor } from "../lib/permissions";
import { parseShape } from "../lib/shape";
import {
  closedLinkLine,
  closedLinkTitle,
  slotDeclarationBody,
  slotDeclarationProblems,
  slotKicker,
  UPLOAD_LINK_PICTURE_PATH,
  UPLOAD_LINK_RENEW_PATH,
  uploadLinkShape,
  uploadLinkToken,
  uploadPageHref,
  type SlotDeclaration,
  type UploadLinkView
} from "../lib/uploadLinkContract";

const VIEW: UploadLinkView = {
  state: "OPEN",
  craft: { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh" },
  stage: { id: "5b1c2d3e-0000-4000-8000-000000000005", name: "Printing the resist" },
  material: null,
  slot: null,
  taskKey: null,
  facts: [{ id: "4d1c2b3a-0000-4000-8000-000000000001", text: "The resist paste holds lime and gum." }],
  expiresAt: "2026-11-19T12:30:00Z",
  contributionId: null
};

const AI_IMAGE: SlotDeclaration = {
  origin: "AI_GENERATED",
  generator: "  ChatGPT, gpt-image-1 ",
  prompt: " A block coated in grey resist paste ",
  caption: " The resist paste on the block ",
  altText: "A carved block coated in grey paste"
};

test("only a token of letters, digits, dashes and underscores is read from the address", () => {
  expect(uploadLinkToken("kvup_pg_Ab-9_x")).toBe("kvup_pg_Ab-9_x");
  expect(uploadLinkToken("kvup_pg_a b")).toBeNull();
  expect(uploadLinkToken("../admin")).toBeNull();
  expect(uploadLinkToken("")).toBeNull();
  expect(uploadLinkToken(null)).toBeNull();
  expect(uploadLinkToken("k".repeat(201))).toBeNull();
});

test("the page and the API addresses carry the token escaped", () => {
  expect(uploadPageHref("kvup_pg_x-y")).toBe("/contributions/pictures/upload?link=kvup_pg_x-y");
  expect(UPLOAD_LINK_PICTURE_PATH("kvup_pg_a/b")).toBe("/upload-links/kvup_pg_a%2Fb/picture");
  expect(UPLOAD_LINK_RENEW_PATH("kvup_pg_x")).toBe("/upload-links/kvup_pg_x/renew");
});

test("the declaration sent through a link carries no craft or facts, which the link already holds", () => {
  expect(slotDeclarationBody(AI_IMAGE)).toEqual({
    origin: "AI_GENERATED",
    generator: "ChatGPT, gpt-image-1",
    prompt: "A block coated in grey resist paste",
    caption: "The resist paste on the block",
    altText: "A carved block coated in grey paste",
    rightsConfirmed: true,
    termsVersion: "2026-11-19"
  });
  expect(slotDeclarationBody({ ...AI_IMAGE, origin: "PHOTOGRAPH" })).toMatchObject({ origin: "PHOTOGRAPH", generator: null, prompt: null });
});

test("an AI picture through a link still names its tool and prompt, and its facts come from the link", () => {
  expect(slotDeclarationProblems(VIEW, { ...AI_IMAGE, generator: " ", prompt: "" })).toEqual(["Name the AI tool and model.", "Give the prompt."]);
  expect(slotDeclarationProblems(VIEW, AI_IMAGE)).toEqual([]);
  expect(slotDeclarationProblems(VIEW, { ...AI_IMAGE, caption: "  " })).toEqual(["Write a caption."]);
});

test("the server's link view parses, and an unknown state or a link without facts is refused", () => {
  expect(parseShape(uploadLinkShape, VIEW)).toEqual(VIEW);
  expect(parseShape(uploadLinkShape, { ...VIEW, stage: null })).toEqual({ ...VIEW, stage: null });
  expect(() => parseShape(uploadLinkShape, { ...VIEW, state: "REVOKED" })).toThrow();
  expect(() => parseShape(uploadLinkShape, { ...VIEW, facts: [] })).toThrow();
});

test("the link names the stage, material or page slot its picture is for", () => {
  expect(slotKicker(VIEW)).toBe("Kutch Ajrakh · Printing the resist");
  expect(slotKicker({ ...VIEW, stage: null, material: { id: "m1", name: "Harda" } })).toBe("Kutch Ajrakh · Harda");
  expect(slotKicker({ ...VIEW, stage: null, slot: "MASTHEAD" })).toBe("Kutch Ajrakh · The first picture of the page");
  expect(slotKicker({ ...VIEW, stage: null })).toBe("Kutch Ajrakh");
});

test("a used or expired link says so and what a new link gives", () => {
  expect(closedLinkTitle({ ...VIEW, state: "USED" })).toBe("This link was used already");
  expect(closedLinkTitle({ ...VIEW, state: "EXPIRED" })).toBe("This link has expired");
  expect(closedLinkLine({ ...VIEW, state: "USED" })).toBe(
    "A picture link takes one picture. Get a new link to give another picture of Kutch Ajrakh for the same facts."
  );
  expect(closedLinkLine({ ...VIEW, state: "EXPIRED" })).toBe(
    "A picture link works for 30 minutes. Get a new link for the same craft and facts, valid for another 30 minutes."
  );
});

test("the link's page is guarded like the other picture pages", () => {
  expect(routeGuardFor("/contributions/pictures/upload")?.gate).toBe("require(PROPOSE_KNOWLEDGE)");
});
