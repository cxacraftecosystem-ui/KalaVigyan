import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { formatCalendarDay } from "@/lib/format";
import {
  checkedMediaAsset,
  checkedMediaJob,
  checkedMediaOptions,
  IDEMPOTENCY_KEY_PATTERN,
  mediaAssetShape,
  mediaJobShape,
  mediaOptionsShape,
  offeredKinds,
  type MediaAsset,
  type MediaJob
} from "@/lib/mediaContract";
import { canShareMedia } from "@/lib/permissions";
import { parseShape, ShapeError } from "@/lib/shape";
import type { User, UserRole } from "@/lib/types";
import nextConfig from "../next.config";

const ROOT = join(__dirname, "..", "..");
const read = (...parts: string[]) => readFileSync(join(ROOT, ...parts), "utf8");
const golden = (name: string): Record<string, unknown> => JSON.parse(read("shared", name));
const PA = "575d3427-7a90-568d-87d5-bb0f1c602591";
const RANG = "eb895bd5-83a3-511a-9e64-ba7e452afea8";
const KUT = "5ced8309-b0f4-571a-8482-4223d1d4fccc";

function job(change: Record<string, unknown> = {}): MediaJob {
  return checkedMediaJob(parseShape(mediaJobShape, { ...golden("media.job.golden.json"), ...change }));
}

function asset(change: Record<string, unknown> = {}): MediaAsset {
  const body = { ...(golden("media.job.golden.json").asset as Record<string, unknown>), ...change };
  return checkedMediaAsset(parseShape(mediaAssetShape, body), "IMAGE");
}

const OPEN = { status: "QUEUED", asset: null, pollAfterSeconds: 3, attempts: 0 };

test("the golden job is a labelled Ajrakh image of stage 6", () => {
  const done = job();
  expect(done.stage).toEqual({ id: PA, ordinal: 6, name: "Pa (alum mordant printing for red)" });
  expect(done.asset?.label.text).toBe("AI illustration");
  expect(done.asset?.altText).toContain("alum in tamarind-seed paste");
});

test("status decides asset, failure and polling, as the backend model does", () => {
  expect(job(OPEN).pollAfterSeconds).toBe(3);
  expect(() => job({ asset: null })).toThrow(ShapeError);
  expect(() => job({ ...OPEN, pollAfterSeconds: null })).toThrow(/poll interval/);
  expect(() => job({ pollAfterSeconds: 3 })).toThrow(/poll interval/);
  expect(() => job({ status: "FAILED", asset: null, refunded: true })).toThrow(/reason/);
  expect(job({ status: "BLOCKED", asset: null, refunded: true, failure: { reason: "BLOCKED", message: "This stage can't be drawn." } }).failure?.message).toBe(
    "This stage can't be drawn."
  );
  expect(() => job({ status: "FAILED", asset: null, failure: { reason: "BLOCKED", message: "x" } })).toThrow(/reason/);
});

test("a video job holding the image file is refused", () => {
  expect(() => job({ kind: "VIDEO" })).toThrow(/video\/mp4/);
  expect(() => checkedMediaAsset(asset(), "VIDEO")).toThrow(ShapeError);
});

test("options are checked against the craft and the kinds still offered", () => {
  const options = parseShape(mediaOptionsShape, golden("media.options.golden.json"));
  expect(checkedMediaOptions(options, "Kutch-Ajrakh")).toBe(options);
  expect(() => checkedMediaOptions(options, "Bagh-Print")).toThrow(/craft\.slug/);
  expect(() => checkedMediaOptions({ ...options, stages: [{ stageId: PA, kinds: ["VIDEO"] }] }, "Kutch-Ajrakh")).toThrow(/kinds/);
  expect(() => checkedMediaOptions({ ...options, kinds: [{ kind: "IMAGE", remainingToday: 0 }] }, "Kutch-Ajrakh")).toThrow(/remainingToday/);
  expect(() => checkedMediaOptions({ ...options, stages: [...options.stages, options.stages[0]] }, "Kutch-Ajrakh")).toThrow(/each stage once/);
});

test("a stage offers only the kinds listed for it, with what is left today", () => {
  const options = parseShape(mediaOptionsShape, golden("media.options.golden.json"));
  expect(offeredKinds(options, PA)).toEqual([{ kind: "IMAGE", remainingToday: 4 }]);
  expect(offeredKinds(options, RANG)).toEqual([{ kind: "IMAGE", remainingToday: 4 }]);
  expect(offeredKinds(options, KUT)).toEqual([]);
  const both = { ...options, kinds: [{ kind: "VIDEO" as const, remainingToday: null }, { kind: "IMAGE" as const, remainingToday: 4 }], stages: [{ stageId: PA, kinds: ["VIDEO" as const, "IMAGE" as const] }] };
  expect(offeredKinds(both, PA).map((offer) => offer.kind)).toEqual(["IMAGE", "VIDEO"]);
});

test("the idempotency key fits the pattern the backend enforces", () => {
  const backend = /IDEMPOTENCY_KEY_PATTERN = r"(.+)"/.exec(read("backend", "app", "schemas", "media.py"))?.[1];
  expect(backend).toBe("^[A-Za-z0-9._:-]{16,160}$");
  expect(IDEMPOTENCY_KEY_PATTERN.source).toBe(backend);
  expect(new RegExp(backend!).test("media:3f2b9c1e-8d4a-4f6b-9e21-7c5d0a1b2c3d")).toBe(true);
});

test("only the roles holding SHARE_MEDIA in the backend see sharing", () => {
  const minimum = /Capability\.SHARE_MEDIA: (\w+),/.exec(read("backend", "app", "core", "roles.py"))?.[1];
  expect(minimum).toBe("PROFESSOR");
  const person = (role: UserRole): User => ({ id: role, email: `${role}@example.com`, name: role, role });
  expect((["STUDENT", "RESEARCHER", "PROFESSOR", "MASTER_ADMIN"] as const).map((role) => canShareMedia(person(role)))).toEqual([false, false, true, true]);
  expect(canShareMedia(null)).toBe(false);
});

test("a generation day prints as that day in every time zone", () => {
  expect(formatCalendarDay("2026-11-16")).toBe("16 Nov 2026");
  expect(formatCalendarDay("2027-01-01")).toBe("01 Jan 2027");
  expect(() => formatCalendarDay("16/11/2026")).toThrow(RangeError);
});

test("the CSP lets images, video and downloads reach the media bucket the Terraform names", async () => {
  const variables = read("infra", "terraform", "variables.tf");
  const defaultOf = (name: string) => new RegExp(`variable "${name}" \\{[^}]*default\\s*=\\s*"([^"]+)"`).exec(variables)?.[1];
  const origin = `https://${defaultOf("bucket_name")}.s3.${defaultOf("aws_region")}.amazonaws.com`;
  expect(origin).toBe("https://kalavigyan-media-626159998512.s3.ap-south-1.amazonaws.com");
  const rules = await nextConfig.headers!();
  const csp = rules[0].headers.find((header) => header.key === "Content-Security-Policy")?.value ?? "";
  const directive = (name: string) => csp.split("; ").find((entry) => entry.startsWith(`${name} `))?.split(" ") ?? [];
  expect(directive("img-src")).toEqual(["img-src", "'self'", "data:", origin, "https:"]);
  expect(directive("media-src")).toEqual(["media-src", "'self'", origin]);
  expect(directive("connect-src")).toContain(origin);
});
