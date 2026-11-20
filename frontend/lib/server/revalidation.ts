import { createHash, timingSafeEqual } from "node:crypto";

export const REVALIDATE_ROUTE = "/api/revalidate";
export const REVALIDATE_SECRET_HEADER = "x-revalidate-secret";
export const REVALIDATE_SECRET_ENV = "WEB_REVALIDATE_SECRET";
export const TARGETS_MAX = 40;
export const NOT_CONFIGURED = "Refreshing pages on request is not set up on this deployment.";
export const NOT_ALLOWED = "This request may not refresh pages.";
export const NOT_TARGETS = `Name the craft and category pages to refresh and their document tags, at most ${TARGETS_MAX} in all.`;

const SLUG = "[A-Za-z0-9-]+";
const PAGE_PATH = new RegExp(`^/(crafts|categories)/${SLUG}(/monograph)?$`);
const PAGE_TAG = new RegExp(`^(craft-page:${SLUG}|monograph-document:(craft|category):${SLUG})$`);
const JSON_HEADERS = { "content-type": "application/json", "cache-control": "no-store" };

export type Revalidation = { paths: string[]; tags: string[] };

type Env = Record<string, string | undefined>;

export type RevalidateDeps = {
  env: Env;
  refreshPath: (path: string) => void;
  refreshTag: (tag: string) => void;
};

export function revalidateSecret(env: Env): string {
  return (env[REVALIDATE_SECRET_ENV] ?? "").trim();
}

export function sameSecret(sent: string | null, expected: string): boolean {
  if (!expected || !sent) return false;
  return timingSafeEqual(digest(sent), digest(expected));
}

export function parsedRevalidation(body: unknown): Revalidation | null {
  if (typeof body !== "object" || body === null || Array.isArray(body)) return null;
  const { paths, tags } = body as Record<string, unknown>;
  if (!isTextList(paths) || !isTextList(tags)) return null;
  const count = paths.length + tags.length;
  if (count === 0 || count > TARGETS_MAX) return null;
  if (!paths.every((path) => PAGE_PATH.test(path)) || !tags.every((tag) => PAGE_TAG.test(tag))) return null;
  return { paths: [...new Set(paths)], tags: [...new Set(tags)] };
}

export async function handleRevalidate(request: Request, deps: RevalidateDeps): Promise<Response> {
  const expected = revalidateSecret(deps.env);
  if (!expected) return answer(503, { detail: NOT_CONFIGURED });
  if (!sameSecret(request.headers.get(REVALIDATE_SECRET_HEADER), expected)) return answer(401, { detail: NOT_ALLOWED });
  const asked = parsedRevalidation(await request.json().catch(() => null));
  if (!asked) return answer(422, { detail: NOT_TARGETS });
  for (const path of asked.paths) deps.refreshPath(path);
  for (const tag of asked.tags) deps.refreshTag(tag);
  return answer(200, { revalidated: asked });
}

function answer(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

function isTextList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === "string");
}

function digest(value: string): Buffer {
  return createHash("sha256").update(value, "utf8").digest();
}
