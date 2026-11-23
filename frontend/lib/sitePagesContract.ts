import { INSTANT, UUID } from "@/lib/answerShapes";
import { boolean, count, list, matching, nullable, object, oneOf, parseShape, text, type Shape } from "@/lib/shape";

export const SITE_PAGES_PATH = "/site/pages";
export const SITE_BUILD_PATH = "/site/build";
export const SITE_REFRESH_PATH = "/site/refresh";
export const STATIC_PAGES_SCHEMA_VERSION = 1;
export const PAGE_REFRESH_SCHEMA_VERSION = 1;
export const STATIC_PAGE_REVALIDATE_SECONDS = 604_800;
export const REFRESH_SCOPES = ["CHANGED", "EVERY", "NAMED"] as const;
export const REFRESH_ORIGINS = ["WEB", "MCP", "NIGHT", "REVIEW"] as const;
export const REFRESH_STATUSES = ["RUNNING", "DONE", "FAILED"] as const;
export const REFRESH_PHASES = ["PAGES", "DOCUMENTS", "REFRESHING", "FINISHED"] as const;

const SLUG = matching(/^\S+$/, "a page slug");

export type StaticPages = { schemaVersion: typeof STATIC_PAGES_SCHEMA_VERSION; crafts: string[]; categories: string[] };
export type SiteBuildState = { configured: boolean; lastTriggeredAt: string | null; nextAllowedAt: string | null };
export type CraftParams = { slug: string };

export type RefreshScope = (typeof REFRESH_SCOPES)[number];
export type RefreshOrigin = (typeof REFRESH_ORIGINS)[number];
export type RefreshJobStatus = (typeof REFRESH_STATUSES)[number];
export type RefreshPhase = (typeof REFRESH_PHASES)[number];

export type RefreshProgress = {
  pagesStale: number;
  pagesRebuilt: number;
  pagesChanged: number;
  documentsStale: number;
  documentsRebuilt: number;
  pagesToRefresh: number;
  pagesRefreshed: number;
  unrefreshed: string[];
  failed: string[];
};

export type RefreshJobView = {
  id: string;
  scope: RefreshScope;
  origin: RefreshOrigin;
  status: RefreshJobStatus;
  phase: RefreshPhase;
  startedBy: string | null;
  clientName: string | null;
  startedAt: string;
  finishedAt: string | null;
  progress: RefreshProgress;
  note: string | null;
};

export type PageRefreshState = {
  schemaVersion: typeof PAGE_REFRESH_SCHEMA_VERSION;
  configured: boolean;
  running: RefreshJobView | null;
  last: RefreshJobView | null;
  nextAllowedAt: string | null;
  everyAllowedAt: string | null;
  mayRefreshEvery: boolean;
};

const staticPagesShape: Shape<StaticPages> = object({
  schemaVersion: oneOf([STATIC_PAGES_SCHEMA_VERSION] as const),
  crafts: list(SLUG),
  categories: list(SLUG)
});

const siteBuildShape: Shape<SiteBuildState> = object({
  configured: boolean,
  lastTriggeredAt: nullable(INSTANT),
  nextAllowedAt: nullable(INSTANT)
});

const refreshProgressShape: Shape<RefreshProgress> = object<RefreshProgress>({
  pagesStale: count,
  pagesRebuilt: count,
  pagesChanged: count,
  documentsStale: count,
  documentsRebuilt: count,
  pagesToRefresh: count,
  pagesRefreshed: count,
  unrefreshed: list(text),
  failed: list(text)
});

const refreshJobShape: Shape<RefreshJobView> = object<RefreshJobView>({
  id: UUID,
  scope: oneOf(REFRESH_SCOPES),
  origin: oneOf(REFRESH_ORIGINS),
  status: oneOf(REFRESH_STATUSES),
  phase: oneOf(REFRESH_PHASES),
  startedBy: nullable(text),
  clientName: nullable(text),
  startedAt: INSTANT,
  finishedAt: nullable(INSTANT),
  progress: refreshProgressShape,
  note: nullable(text)
});

const pageRefreshShape: Shape<PageRefreshState> = object<PageRefreshState>({
  schemaVersion: oneOf([PAGE_REFRESH_SCHEMA_VERSION] as const),
  configured: boolean,
  running: nullable(refreshJobShape),
  last: nullable(refreshJobShape),
  nextAllowedAt: nullable(INSTANT),
  everyAllowedAt: nullable(INSTANT),
  mayRefreshEvery: boolean
});

export function parseStaticPages(raw: unknown): StaticPages {
  return parseShape(staticPagesShape, raw);
}

export function parseSiteBuildState(raw: unknown): SiteBuildState {
  return parseShape(siteBuildShape, raw);
}

export function parsePageRefreshState(raw: unknown): PageRefreshState {
  return parseShape(pageRefreshShape, raw);
}

export function instantAhead(value: string | null, now: Date): Date | null {
  if (!value) return null;
  const until = new Date(value);
  return until.getTime() > now.getTime() ? until : null;
}

export function buildWaitsUntil(state: SiteBuildState, now: Date): Date | null {
  return instantAhead(state.nextAllowedAt, now);
}

export type SiteBuildStatus = "loading" | "unset" | "started" | "waiting" | "last" | "never";

export function siteBuildStatus(state: SiteBuildState | null, now: Date, started: boolean): SiteBuildStatus {
  if (!state) return "loading";
  if (!state.configured) return "unset";
  if (started) return "started";
  if (buildWaitsUntil(state, now)) return "waiting";
  return state.lastTriggeredAt ? "last" : "never";
}
