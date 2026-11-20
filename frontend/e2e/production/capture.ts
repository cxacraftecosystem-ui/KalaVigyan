import type { Page, Request } from "@playwright/test";

import { CITED_CONTENT } from "./checks";
import {
  ANSWER_SCOPE,
  BUSY_PATTERN,
  FULL_OPACITY,
  MIN_PICTURE_PX,
  REGION_MARKER,
  REGION_PANEL,
  busyProblems,
  clusterProblems,
  emptyPictureProblems,
  moleculeProblems,
  opacityProblems,
  regionProblems,
  repeatProblems,
  themeProblems,
  tileProblems,
  unpaintedNotes
} from "./gates";
import type { Scheme } from "./matrix";
import { answerRepeats, busyText, citationClusters, emptyPictures, opacityAtCapture, regionRunPx, shownTheme } from "./sight";
import { scanTiles } from "./tiles";

const SETTLE_MS = 700;
const IDLE_TIMEOUT_MS = 20_000;
const BUSY_TIMEOUT_MS = 30_000;
const POLL_MS = 250;
const QUIET_MS = 500;
const QUIET_TIMEOUT_MS = 15_000;
const SCROLL_SHARE = 0.8;
const SCROLL_PAUSE_MS = 120;
const SCROLL_STEPS_MAX = 400;
const MOLECULE_TIMEOUT_MS = 30_000;
const ANIMATION_TIMEOUT_MS = 5_000;
const AFTER_TOP_MS = 300;
const UNTRACKED_REQUESTS: ReadonlySet<string> = new Set(["eventsource", "websocket", "media"]);
const MOLECULE = '[data-testid="molecule-3d"]';
const MOLECULE_PENDING: ReadonlySet<string> = new Set(["waiting", "loading"]);
const SEGMENT_SCREENS = 8;
const MAX_CAPTURE_DEVICE_PX = 16_384;
const MAX_WEBKIT_SHOT_DEVICE_PX = 32_767;
const SHOT_TIMEOUT_MS = 90_000;

async function busyNow(page: Page): Promise<string[] | null> {
  return page.evaluate(busyText, { citedSelector: CITED_CONTENT, pattern: BUSY_PATTERN }).catch(() => null);
}

async function waitForBusyText(page: Page): Promise<string[]> {
  const deadline = Date.now() + BUSY_TIMEOUT_MS;
  for (;;) {
    const busy = await busyNow(page);
    if ((busy && busy.length === 0) || Date.now() >= deadline) return busy ?? [];
    await page.waitForTimeout(POLL_MS);
  }
}

export async function settle(page: Page): Promise<string[]> {
  await page.waitForLoadState("networkidle", { timeout: IDLE_TIMEOUT_MS }).catch(() => undefined);
  const busy = await waitForBusyText(page);
  await page.waitForTimeout(SETTLE_MS);
  return busyProblems(busy);
}

export class NetworkQuiet {
  private readonly open = new Set<Request>();
  private changedAt = Date.now();

  constructor(private readonly page: Page) {
    const finished = (request: Request) => {
      if (this.open.delete(request)) this.changedAt = Date.now();
    };
    page.on("request", (request) => {
      if (UNTRACKED_REQUESTS.has(request.resourceType())) return;
      this.open.add(request);
      this.changedAt = Date.now();
    });
    page.on("requestfinished", finished);
    page.on("requestfailed", finished);
  }

  async settled(): Promise<boolean> {
    const deadline = Date.now() + QUIET_TIMEOUT_MS;
    while (Date.now() < deadline) {
      if (this.open.size === 0 && Date.now() - this.changedAt >= QUIET_MS) return true;
      await this.page.waitForTimeout(POLL_MS);
    }
    return false;
  }
}

async function scrollToEnd(page: Page): Promise<void> {
  const step = Math.round((page.viewportSize()?.height ?? 800) * SCROLL_SHARE);
  for (let index = 0; index < SCROLL_STEPS_MAX; index += 1) {
    const atEnd = await page.evaluate((by) => {
      window.scrollBy({ top: by, left: 0, behavior: "instant" });
      return window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2;
    }, step);
    await page.waitForTimeout(SCROLL_PAUSE_MS);
    if (atEnd) return;
  }
}

async function moleculeStatuses(page: Page): Promise<string[]> {
  const read = () =>
    page.locator(MOLECULE).evaluateAll((nodes) => nodes.filter((node) => node.checkVisibility()).map((node) => node.getAttribute("data-status") ?? ""));
  const deadline = Date.now() + MOLECULE_TIMEOUT_MS;
  for (;;) {
    const statuses = await read();
    if (!statuses.some((status) => MOLECULE_PENDING.has(status)) || Date.now() >= deadline) return statuses;
    await page.waitForTimeout(POLL_MS);
  }
}

async function animationsEnded(page: Page): Promise<void> {
  await page
    .waitForFunction(
      () => document.getAnimations().every((animation) => animation.playState !== "running" || animation.effect?.getComputedTiming().endTime === Infinity),
      undefined,
      { timeout: ANIMATION_TIMEOUT_MS, polling: POLL_MS }
    )
    .catch(() => undefined);
}

export async function readyForCapture(page: Page, network: NetworkQuiet): Promise<string[]> {
  await scrollToEnd(page);
  await network.settled();
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  const molecules = await moleculeStatuses(page);
  const busy = await waitForBusyText(page);
  await network.settled();
  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: "instant" }));
  await animationsEnded(page);
  await page.waitForTimeout(AFTER_TOP_MS);
  return [...moleculeProblems(molecules), ...busyProblems(busy)];
}

export async function sightProblems(page: Page, scheme: Scheme | null): Promise<string[]> {
  const screenHeight = page.viewportSize()?.height ?? 1;
  return [
    ...themeProblems(await page.evaluate(shownTheme), scheme),
    ...opacityProblems(await page.evaluate(opacityAtCapture, FULL_OPACITY)),
    ...clusterProblems(await page.evaluate(citationClusters)),
    ...repeatProblems(await page.evaluate(answerRepeats, ANSWER_SCOPE)),
    ...emptyPictureProblems(await page.evaluate(emptyPictures, MIN_PICTURE_PX)),
    ...regionProblems(await page.evaluate(regionRunPx, { panel: REGION_PANEL, marker: REGION_MARKER }), screenHeight)
  ];
}

export type Captured = { problems: string[]; notes: string[] };

type Sheet = { width: number; height: number; screen: number; ratio: number };

async function sheetOf(page: Page): Promise<Sheet> {
  const measured = await page.evaluate(() => {
    const body = document.body;
    const root = document.documentElement;
    return {
      width: Math.max(body.scrollWidth, root.scrollWidth, body.offsetWidth, root.offsetWidth, body.clientWidth, root.clientWidth),
      height: Math.max(body.scrollHeight, root.scrollHeight, body.offsetHeight, root.offsetHeight, body.clientHeight, root.clientHeight),
      ratio: window.devicePixelRatio
    };
  });
  return { ...measured, screen: page.viewportSize()?.height ?? 0 };
}

export function segmentScreens(sheet: Pick<Sheet, "screen" | "ratio">): number {
  return Math.max(1, Math.min(SEGMENT_SCREENS, Math.floor(MAX_CAPTURE_DEVICE_PX / (sheet.screen * sheet.ratio))));
}

async function paintedFlat(page: Page, sheet: Sheet, tileHeight: number, fromTile: number): Promise<number[]> {
  const flat: number[] = [];
  const span = segmentScreens(sheet);
  for (let tile = fromTile; tile * sheet.screen < sheet.height; tile += span) {
    const top = tile * sheet.screen;
    const clip = { x: 0, y: top, width: sheet.width, height: Math.min(sheet.screen * span, sheet.height - top) };
    const scan = await scanTiles(await page.screenshot({ fullPage: true, clip }), tileHeight);
    flat.push(...scan.flat.map((index) => index + tile));
  }
  return flat;
}

export async function judgeCapture(page: Page, png: Buffer): Promise<Captured> {
  const sheet = await sheetOf(page);
  const tileHeight = Math.round(sheet.screen * sheet.ratio);
  if (tileHeight < 1) return { problems: [], notes: [] };
  const shot = await scanTiles(png, tileHeight);
  const [firstFlat] = shot.flat;
  if (firstFlat === undefined) return { problems: [], notes: [] };
  const painted = await paintedFlat(page, sheet, tileHeight, Math.max(0, firstFlat - 1));
  return { problems: tileProblems({ ...shot, flat: painted }), notes: unpaintedNotes(shot.flat, painted, sheet.screen) };
}

export function shotHeight(height: number, ratio: number): number | null {
  const most = Math.floor(MAX_WEBKIT_SHOT_DEVICE_PX / ratio);
  return height > most ? most : null;
}

export async function captureScreen(page: Page, path: string): Promise<Captured> {
  const webkit = page.context().browser()?.browserType().name() === "webkit";
  const sheet = await sheetOf(page);
  const capped = webkit ? shotHeight(sheet.height, sheet.ratio) : null;
  if (capped === null) return judgeCapture(page, await page.screenshot({ path, fullPage: true, timeout: SHOT_TIMEOUT_MS }));
  const judged = await judgeCapture(page, await page.screenshot({ path, fullPage: true, timeout: SHOT_TIMEOUT_MS, clip: { x: 0, y: 0, width: sheet.width, height: capped } }));
  return { ...judged, notes: [...judged.notes, `the page runs ${sheet.height}px, taller than one WebKit screenshot holds, so the capture keeps its first ${capped}px`] };
}
