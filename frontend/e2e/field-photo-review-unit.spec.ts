import { expect, test } from "@playwright/test";

import { fieldPhotoQueueShape, type FieldPhoto, type FieldPhotoQueue } from "@/lib/fieldPhotoReviewContract";
import {
  cropFromTrims,
  cropProblem,
  decisionBody,
  draftProblem,
  firstDraft,
  NO_TRIMS,
  screenedLine,
  stateOptions,
  trimsOfCrop,
  withDecided,
  type PhotoDraft
} from "@/lib/fieldPhotoReviewView";
import { canAccessRoute, ROUTE_GUARDS } from "@/lib/permissions";
import { parseShape } from "@/lib/shape";
import type { User } from "@/lib/types";

const SHA = "b".repeat(64);
const SCREENED = { verdict: "CLEAR" as const, flags: [], reasons: [], nearestDistance: null, model: "gemini-test-flash-lite", screenedAt: "2026-11-21T03:30:00Z" };

const PHOTO: FieldPhoto = {
  id: "5ca1ab1e-0000-4000-8000-0000000000f1",
  itemId: "FIELD_REPOSITORY:fr-img-1",
  origin: "FIELD_REPOSITORY",
  publisher: "Field Repository",
  sha256: SHA,
  caption: "Washing the printed cloth in the river",
  alt: "A printer rinses a length of cloth",
  takenOn: "2026-03-15",
  crafts: ["Ajrakh Print of Kutch"],
  placements: ["Asha Demo"],
  people: [{ name: "Asha Demo", kind: "ARTISAN" }],
  credit: "Asha Demo · Ajrakhpur workshop, 15 Mar 2026 · Field Repository",
  workshop: "Ajrakhpur workshop",
  statement: "Shared by the Field Repository with the artisan's consent.",
  rightsHolder: "IIT Kharagpur",
  licence: null,
  width: 2400,
  height: 1600,
  mime: "image/jpeg",
  fileUrl: "https://bucket.test/media/field-voices/copy.jpg",
  state: "WAITING",
  risk: "CLEAR",
  masterOnly: false,
  screen: SCREENED,
  decision: null,
  history: []
};

const draft = (over: Partial<PhotoDraft>): PhotoDraft => ({ decision: "SHOW", reason: null, note: "", trims: NO_TRIMS, clearFlags: false, ...over });
const person = (role: User["role"], capabilities: string[] = []): User => ({ id: role, email: `${role}@example.org`, name: role, role, capabilities }) as User;

test("the field photographs page is guarded by the capability the API requires", () => {
  const gates = Object.fromEntries(ROUTE_GUARDS.map((guard) => [guard.path, guard.gate]));
  expect(gates["/admin/field-photos"]).toBe("require(REVIEW_CONTRIBUTIONS)");
  expect(canAccessRoute(person("ADMIN", ["REVIEW_CONTRIBUTIONS"]), "/admin/field-photos")).toBe(true);
  expect(canAccessRoute(person("PROFESSOR"), "/admin/field-photos")).toBe(false);
});

test("a queue answer is read field by field and a field the page does not know is refused", () => {
  const queue: FieldPhotoQueue = { schemaVersion: 1, state: "WAITING", visibility: "HIDDEN", counts: { waiting: 1, shown: 0, hidden: 0 }, cursor: null, nextCursor: null, items: [PHOTO] };
  expect(parseShape(fieldPhotoQueueShape, queue)).toEqual(queue);
  expect(() => parseShape(fieldPhotoQueueShape, { ...queue, items: [{ ...PHOTO, objectKey: "media/x.jpg" }] })).toThrow("no such field");
});

test("trimming each edge by a share of the photograph keeps the region between them", () => {
  expect(cropFromTrims({ top: 10, bottom: 5, left: 20, right: 0 }, 2400, 1600)).toEqual({ left: 480, top: 160, width: 1920, height: 1360 });
  expect(trimsOfCrop({ left: 480, top: 160, width: 1920, height: 1360 }, 2400, 1600)).toEqual({ top: 10, bottom: 5, left: 20, right: 0 });
});

test("a crop leaves part of the photograph out and keeps at least sixty-four pixels a side", () => {
  expect(cropProblem({ left: 0, top: 0, width: 2400, height: 1600 }, 2400, 1600)).toBe("Trim at least one edge, or choose Show to show all of it.");
  expect(cropProblem({ left: 0, top: 0, width: 63, height: 1600 }, 2400, 1600)).toBe("Keep at least 64 pixels on each side.");
  expect(cropProblem({ left: 10, top: 0, width: 2390, height: 1600 }, 2400, 1600)).toBeNull();
});

test("a decision says what it still lacks before it is sent", () => {
  const flagged = { ...PHOTO, risk: "IDENTITY" as const, masterOnly: true };
  expect(draftProblem(draft({ decision: "HIDE" }), PHOTO, false)).toBe("Choose why it stays hidden.");
  expect(draftProblem(draft({ decision: "HIDE", reason: "OTHER", note: " " }), PHOTO, false)).toBe("Say in the note why it stays hidden.");
  expect(draftProblem(draft({}), { ...PHOTO, screen: null }, false)).toBe("The screens have not looked at it yet. Screen the waiting photographs first.");
  expect(draftProblem(draft({}), flagged, false)).toBe("Only a Master Admin can show this photograph. You can keep it hidden.");
  expect(draftProblem(draft({}), flagged, true)).toBe("Clear the screen's flag, or show a crop that leaves the region out.");
  expect(draftProblem(draft({ clearFlags: true }), flagged, true)).toBe("Say in the note why the screen's flag is wrong.");
  expect(draftProblem(draft({ clearFlags: true, note: "A printed block, not a card" }), flagged, true)).toBeNull();
  expect(draftProblem(draft({ decision: "HIDE", reason: "NOT_AGREED" }), flagged, false)).toBeNull();
});

test("the body sends a reason only to hide, a crop only to crop and a cleared flag only to show", () => {
  const hidden = decisionBody(draft({ decision: "HIDE", reason: "PRIVATE_PLACE", note: "  A family home  ", trims: { top: 10, bottom: 0, left: 0, right: 0 }, clearFlags: true }), PHOTO);
  expect(hidden).toEqual({ decision: "HIDE", seenSha256: SHA, reason: "PRIVATE_PLACE", note: "A family home", crop: null, clearFlags: false });
  const cropped = decisionBody(draft({ decision: "CROP", reason: "OTHER", trims: { top: 0, bottom: 0, left: 0, right: 25 } }), PHOTO);
  expect(cropped).toEqual({ decision: "CROP", seenSha256: SHA, reason: null, note: null, crop: { left: 0, top: 0, width: 1800, height: 1600 }, clearFlags: false });
});

test("a shown or flagged photograph opens on keeping it hidden and a clear one on showing it", () => {
  expect(firstDraft(PHOTO).decision).toBe("SHOW");
  expect(firstDraft({ ...PHOTO, state: "SHOWN" }).decision).toBe("HIDE");
  expect(firstDraft({ ...PHOTO, masterOnly: true }).decision).toBe("HIDE");
});

test("a decision moves its photograph between the counts and replaces it in place", () => {
  const queue: FieldPhotoQueue = { schemaVersion: 1, state: "WAITING", visibility: "SHOWN", counts: { waiting: 3, shown: 1, hidden: 0 }, cursor: null, nextCursor: null, items: [PHOTO] };
  const shown = { ...PHOTO, state: "SHOWN" as const };
  const next = withDecided(queue, shown);
  expect(next.counts).toEqual({ waiting: 2, shown: 2, hidden: 0 });
  expect(next.items).toEqual([shown]);
  expect(stateOptions(next.counts).map((option) => option.label)).toEqual(["Waiting 2", "Shown 2", "Hidden 0"]);
});

test("a screening run reports what it looked at in words", () => {
  expect(screenedLine({ ok: true, screened: 0, flagged: 0, unscreened: 0, missing: [] })).toBe("Every waiting photograph has been screened.");
  expect(screenedLine({ ok: false, screened: 4, flagged: 1, unscreened: 0, missing: ["a", "b"] })).toBe(
    "Screened 4 photographs: 1 flagged, 0 not looked at automatically. The stored copies of 2 photographs are missing."
  );
});
