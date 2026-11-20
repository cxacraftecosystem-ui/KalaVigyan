import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { ShapeError } from "@/lib/shape";
import {
  STATIC_PAGE_REVALIDATE_SECONDS,
  buildWaitsUntil,
  parseSiteBuildState,
  parseStaticPages,
  siteBuildStatus,
  type SiteBuildState,
  type StaticPages
} from "@/lib/sitePagesContract";

const SHARED = join(__dirname, "..", "..", "shared");
const CRAFT_ROUTE = join(__dirname, "..", "app", "(reading)", "crafts", "[slug]", "page.tsx");
const NOW = new Date("2026-11-20T00:30:00+00:00");

const golden = (): StaticPages => JSON.parse(readFileSync(join(SHARED, "site.pages.golden.json"), "utf8")) as StaticPages;

const built = (changes: Partial<SiteBuildState> = {}): SiteBuildState => ({
  configured: true,
  lastTriggeredAt: "2026-11-20T00:25:00+00:00",
  nextAllowedAt: null,
  ...changes
});

test("the static page list parses exactly as the backend writes it", () => {
  expect(parseStaticPages(golden())).toEqual(golden());
});

test("a static page list off its contract is refused", () => {
  expect(() => parseStaticPages({ ...golden(), schemaVersion: 2 })).toThrow(ShapeError);
  expect(() => parseStaticPages({ ...golden(), crafts: ["Bagh Print"] })).toThrow(ShapeError);
  expect(() => parseStaticPages({ ...golden(), extra: true })).toThrow(ShapeError);
});

test("the craft route keeps its pages for the day the nightly build refreshes", () => {
  const route = readFileSync(CRAFT_ROUTE, "utf8");
  expect(STATIC_PAGE_REVALIDATE_SECONDS).toBe(24 * 60 * 60);
  expect(route).toContain(`export const revalidate = ${STATIC_PAGE_REVALIDATE_SECONDS};`);
  expect(route).toContain("export async function generateStaticParams");
});

test("the build state parses and a refused shape throws", () => {
  expect(parseSiteBuildState(built())).toEqual(built());
  expect(() => parseSiteBuildState({ ...built(), lastTriggeredAt: "yesterday" })).toThrow(ShapeError);
  expect(() => parseSiteBuildState({ configured: true })).toThrow(ShapeError);
});

test("a build waits only while its next start lies ahead", () => {
  expect(buildWaitsUntil(built({ nextAllowedAt: "2026-11-20T00:35:00+00:00" }), NOW)).toEqual(new Date("2026-11-20T00:35:00Z"));
  expect(buildWaitsUntil(built({ nextAllowedAt: "2026-11-20T00:29:59+00:00" }), NOW)).toBeNull();
  expect(buildWaitsUntil(built(), NOW)).toBeNull();
});

test("the control offers a build only when the hook is set and no build is waiting", () => {
  expect(siteBuildStatus(null, NOW, false)).toBe("loading");
  expect(siteBuildStatus(built({ configured: false }), NOW, false)).toBe("unset");
  expect(siteBuildStatus(built(), NOW, true)).toBe("started");
  expect(siteBuildStatus(built({ nextAllowedAt: "2026-11-20T00:35:00+00:00" }), NOW, false)).toBe("waiting");
  expect(siteBuildStatus(built(), NOW, false)).toBe("last");
  expect(siteBuildStatus(built({ lastTriggeredAt: null }), NOW, false)).toBe("never");
});
