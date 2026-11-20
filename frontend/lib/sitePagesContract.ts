import { INSTANT } from "@/lib/answerShapes";
import { boolean, list, matching, nullable, object, oneOf, parseShape, type Shape } from "@/lib/shape";

export const SITE_PAGES_PATH = "/site/pages";
export const SITE_BUILD_PATH = "/site/build";
export const STATIC_PAGES_SCHEMA_VERSION = 1;
export const STATIC_PAGE_REVALIDATE_SECONDS = 86_400;

const SLUG = matching(/^\S+$/, "a page slug");

export type StaticPages = { schemaVersion: typeof STATIC_PAGES_SCHEMA_VERSION; crafts: string[]; categories: string[] };
export type SiteBuildState = { configured: boolean; lastTriggeredAt: string | null; nextAllowedAt: string | null };
export type CraftParams = { slug: string };

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

export function parseStaticPages(raw: unknown): StaticPages {
  return parseShape(staticPagesShape, raw);
}

export function parseSiteBuildState(raw: unknown): SiteBuildState {
  return parseShape(siteBuildShape, raw);
}

export function buildWaitsUntil(state: SiteBuildState, now: Date): Date | null {
  if (!state.nextAllowedAt) return null;
  const until = new Date(state.nextAllowedAt);
  return until.getTime() > now.getTime() ? until : null;
}

export type SiteBuildStatus = "loading" | "unset" | "started" | "waiting" | "last" | "never";

export function siteBuildStatus(state: SiteBuildState | null, now: Date, started: boolean): SiteBuildStatus {
  if (!state) return "loading";
  if (!state.configured) return "unset";
  if (started) return "started";
  if (buildWaitsUntil(state, now)) return "waiting";
  return state.lastTriggeredAt ? "last" : "never";
}
