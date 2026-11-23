import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import {
  jobOutcome,
  jobSummary,
  mayStartEvery,
  nextReadIn,
  REFRESH_POLL_MS,
  refreshStatus,
  refreshSteps,
  startedByLine
} from "@/lib/pageRefreshView";
import { ShapeError } from "@/lib/shape";
import { parsePageRefreshState, SITE_REFRESH_PATH, type PageRefreshState, type RefreshJobView } from "@/lib/sitePagesContract";

const SHARED = join(__dirname, "..", "..", "shared");
const BUILD_CARD = join(__dirname, "..", "components", "admin", "SiteBuildCard.tsx");
const NOW = new Date("2026-11-23T06:45:00Z");

const golden = (): PageRefreshState => JSON.parse(readFileSync(join(SHARED, "site.refresh.golden.json"), "utf8")) as PageRefreshState;
const running = (): RefreshJobView => golden().running as RefreshJobView;
const last = (): RefreshJobView => golden().last as RefreshJobView;
const idle = (changes: Partial<PageRefreshState> = {}): PageRefreshState => ({ ...golden(), running: null, nextAllowedAt: null, ...changes });

test("the refresh state parses exactly as the backend writes it", () => {
  expect(SITE_REFRESH_PATH).toBe("/site/refresh");
  expect(parsePageRefreshState(golden())).toEqual(golden());
});

test("a refresh state off its contract is refused", () => {
  expect(() => parsePageRefreshState({ ...golden(), schemaVersion: 2 })).toThrow(ShapeError);
  expect(() => parsePageRefreshState({ ...golden(), running: { ...running(), phase: "WAITING" } })).toThrow(ShapeError);
  expect(() => parsePageRefreshState({ ...golden(), running: { ...running(), progress: { ...running().progress, pagesStale: -1 } } })).toThrow(ShapeError);
  expect(() => parsePageRefreshState({ ...golden(), nextAllowedAt: "soon" })).toThrow(ShapeError);
  expect(() => parsePageRefreshState({ ...golden(), extra: true })).toThrow(ShapeError);
});

test("the running job has rebuilt its 7 pages and is rebuilding its stored documents", () => {
  const job = running();
  expect(job.phase).toBe("DOCUMENTS");
  expect(job.progress.pagesRebuilt).toBe(7);
  expect(refreshSteps(job)).toEqual([
    { phase: "PAGES", label: "Rebuild the pages", count: "7 of 7 rebuilt, 5 changed", state: "done" },
    { phase: "DOCUMENTS", label: "Rebuild the stored documents", count: "0 of 3 rebuilt", state: "current" },
    { phase: "REFRESHING", label: "Refresh the pages on the site", count: null, state: "ahead" }
  ]);
  expect(startedByLine(job)).toBe("Started by Admin Reviewer through Claude");
  expect(jobOutcome(job)).toBe("running");
});

test("the last job finished with a page left unrefreshed and a document not rebuilt", () => {
  const job = last();
  expect(refreshSteps(job).map((step) => [step.state, step.count])).toEqual([
    ["done", "2 of 2 rebuilt, 2 changed"],
    ["done", "1 of 1 rebuilt"],
    ["done", "2 of 3 refreshed"]
  ]);
  expect(jobOutcome(job)).toBe("partial");
  expect(jobSummary(job.progress)).toBe("2 of 2 pages rebuilt (2 changed), 1 of 1 stored documents rebuilt, 2 of 3 pages refreshed on the site.");
  expect(startedByLine(job)).toBe("Started by review decisions");
  expect(job.note).toBe("The refresh stopped at its time limit; the night rebuilds what is left.");
});

test("a job's outcome and starter follow its status and origin", () => {
  const job = last();
  const clean = { ...job.progress, unrefreshed: [], failed: [] };
  expect(jobOutcome({ ...job, progress: clean })).toBe("clean");
  expect(jobOutcome({ ...job, status: "FAILED" })).toBe("failed");
  expect(startedByLine({ ...job, origin: "NIGHT" })).toBe("Started by the night's upkeep");
  expect(startedByLine({ ...job, origin: "WEB", startedBy: "Master Admin" })).toBe("Started by Master Admin");
  expect(startedByLine({ ...job, origin: "MCP", startedBy: "Admin Reviewer", clientName: null })).toBe("Started by Admin Reviewer");
});

test("the card reads again every five seconds while a refresh runs, and once when its wait ends", () => {
  expect(REFRESH_POLL_MS).toBe(5_000);
  expect(refreshStatus(null, NOW)).toBe("loading");
  expect(nextReadIn(null, NOW)).toBeNull();
  expect(refreshStatus(golden(), NOW)).toBe("running");
  expect(nextReadIn(golden(), NOW)).toBe(5_000);
  expect(refreshStatus(idle({ nextAllowedAt: "2026-11-23T06:50:00Z" }), NOW)).toBe("waiting");
  expect(nextReadIn(idle({ nextAllowedAt: "2026-11-23T06:50:00Z" }), NOW)).toBe(5 * 60 * 1000);
  expect(nextReadIn(idle({ nextAllowedAt: "2026-11-23T06:45:00.500Z" }), NOW)).toBe(1_000);
  expect(refreshStatus(idle({ nextAllowedAt: "2026-11-23T06:44:59Z" }), NOW)).toBe("ready");
  expect(nextReadIn(idle(), NOW)).toBeNull();
});

test("every page may be refreshed only by the Master Admin, when nothing runs or waits", () => {
  const master = idle({ mayRefreshEvery: true });
  expect(mayStartEvery(golden(), NOW)).toBe(false);
  expect(mayStartEvery(idle(), NOW)).toBe(false);
  expect(mayStartEvery(master, NOW)).toBe(true);
  expect(mayStartEvery({ ...master, running: running() }, NOW)).toBe(false);
  expect(mayStartEvery({ ...master, nextAllowedAt: "2026-11-23T06:50:00Z" }, NOW)).toBe(false);
  expect(mayStartEvery({ ...master, everyAllowedAt: "2026-11-24T06:00:00Z" }, NOW)).toBe(false);
  expect(mayStartEvery(null, NOW)).toBe(false);
});

test("the site build card no longer says the night starts a build", () => {
  const card = readFileSync(BUILD_CARD, "utf8");
  expect(card).not.toContain("starts each night");
  expect(card).toContain("The night starts no build; it refreshes only the pages that changed.");
});
