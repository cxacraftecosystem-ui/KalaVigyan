import type { APIRequestContext } from "@playwright/test";

import { COMPONENT_HOMES, type HomeRecord } from "../../lib/componentHomes";
import { isPreview, PRODUCTION_ORIGIN } from "../production/preview";

export type SubjectKind = "craft" | "family" | "category";
export type DocumentComponent = { label: string; kind: string };
export type SubjectPage = { path: string; slug: string; subject: SubjectKind; curated: boolean; authored: boolean; components: DocumentComponent[] };
export type BorrowedCase = { label: string; kind: string; page: SubjectPage; root: string | null; frame: number };
export type HomeEntry = HomeRecord;

export const AUTHORED_PATH = "/crafts/Kutch-Ajrakh";
const PAGES_PATH = "/api/site/pages";
const STRUCTURE_KIND = "answer_block";
const CATALOGUE_PATH = "/api/crafts/catalogue";
const FETCHES_AT_ONCE = 3;
const RETRY_WAITS_MS = [2000, 5000, 15000, 30000, 60000];

type DocumentBody = { subjectKind?: string; subjectSlug?: string; shell?: string | null; content?: { components?: DocumentComponent[] } };

export function homeOf(label: string): HomeEntry | null {
  return Object.hasOwn(COMPONENT_HOMES.homes, label) ? COMPONENT_HOMES.homes[label] : null;
}

export function subjectPath(subject: SubjectKind, slug: string): string {
  return subject === "category" ? `/categories/${slug}` : `/crafts/${slug}`;
}

export function subjectPage(body: DocumentBody, asked: "craft" | "category", slug: string): SubjectPage | null {
  const components = body.content?.components ?? [];
  const kind = body.subjectKind;
  if (kind !== "craft" && kind !== "family" && kind !== "category") return null;
  const subject: SubjectKind = asked === "category" ? "category" : kind;
  return {
    path: subjectPath(subject, slug),
    slug,
    subject,
    curated: components.some((component) => component.kind === STRUCTURE_KIND),
    authored: typeof body.shell === "string",
    components: components.map((component) => ({ label: component.label, kind: component.kind }))
  };
}

export function retryable(status: number): boolean {
  return status === 429 || status >= 500;
}

async function read(request: APIRequestContext, path: string): Promise<unknown> {
  for (let attempt = 0; attempt < RETRY_WAITS_MS.length; attempt += 1) {
    const response = await request.get(path, { failOnStatusCode: false, timeout: 60_000 }).catch(() => null);
    if (response?.ok()) return response.json();
    if (response && !retryable(response.status())) return null;
    await new Promise((resolve) => setTimeout(resolve, RETRY_WAITS_MS[attempt]));
  }
  throw new Error(`the site did not answer ${path}`);
}

export function apiOrigin(site: string): string {
  return !site || isPreview(site) ? PRODUCTION_ORIGIN : new URL(site).origin;
}

async function documentOf(request: APIRequestContext, origin: string, [asked, slug]: ["craft" | "category", string]): Promise<SubjectPage | null> {
  const path = asked === "category" ? `/api/categories/${encodeURIComponent(slug)}/monograph` : `/api/crafts/${encodeURIComponent(slug)}/monograph`;
  const body = await read(request, `${origin}${path}`);
  return body ? subjectPage(body as DocumentBody, asked, slug) : null;
}

type CatalogueCraft = { slug?: unknown; depth?: { claims?: unknown } | null };

export function craftsWithClaims(crafts: readonly CatalogueCraft[]): string[] {
  return crafts.flatMap((craft) => (typeof craft.slug === "string" && typeof craft.depth?.claims === "number" && craft.depth.claims > 0 ? [craft.slug] : []));
}

async function askedSubjects(request: APIRequestContext, origin: string): Promise<["craft" | "category", string][]> {
  const listed = ((await read(request, `${origin}${PAGES_PATH}`)) ?? {}) as { crafts?: string[]; categories?: string[] };
  const catalogue = ((await read(request, `${origin}${CATALOGUE_PATH}`)) ?? {}) as { crafts?: CatalogueCraft[] };
  const known = new Set(listed.crafts ?? []);
  const crafts = craftsWithClaims(catalogue.crafts ?? []).filter((slug) => known.has(slug));
  return [...(listed.categories ?? []).map((slug) => ["category", slug] as ["category", string]), ...crafts.map((slug) => ["craft", slug] as ["craft", string])];
}

export async function subjectPages(request: APIRequestContext, site: string): Promise<SubjectPage[]> {
  const origin = apiOrigin(site);
  const asked = await askedSubjects(request, origin);
  const found: SubjectPage[] = [];
  for (let at = 0; at < asked.length; at += FETCHES_AT_ONCE) {
    const batch = await Promise.all(asked.slice(at, at + FETCHES_AT_ONCE).map((item) => documentOf(request, origin, item)));
    found.push(...batch.filter((page): page is SubjectPage => page !== null));
  }
  return found;
}

export function pageKind(page: SubjectPage): string {
  if (page.subject !== "craft") return page.subject;
  return page.curated ? "curated craft" : "generated craft";
}

export function borrowedCases(pages: readonly SubjectPage[]): BorrowedCase[] {
  const cases: BorrowedCase[] = [];
  const covered = new Set<string>();
  const ordered = [...pages].filter((page) => !page.authored).sort((a, b) => kindRank(a) - kindRank(b));
  for (const page of ordered) {
    for (const component of page.components) {
      const home = homeOf(component.label);
      const key = `${component.label}@${pageKind(page)}`;
      if (!home || home.kind !== component.kind || covered.has(key)) continue;
      covered.add(key);
      cases.push({ label: component.label, kind: component.kind, page, root: home.root, frame: home.within ? 2 : home.frame.length });
    }
  }
  return cases;
}

function kindRank(page: SubjectPage): number {
  return ["category", "family", "curated craft", "generated craft"].indexOf(pageKind(page));
}

export function pagesToVisit(cases: readonly BorrowedCase[], pages: readonly SubjectPage[]): SubjectPage[] {
  const chosen = new Map<string, SubjectPage>();
  for (const found of cases) chosen.set(found.page.path, found.page);
  for (const page of pages) {
    if (page.authored) continue;
    const kind = pageKind(page);
    if (![...chosen.values()].some((known) => pageKind(known) === kind)) chosen.set(page.path, page);
  }
  return [...chosen.values()];
}

export function sameText(a: string, b: string): number {
  const left = normalised(a);
  const right = normalised(b);
  let at = 0;
  while (at < left.length && at < right.length && left[at] === right[at]) at += 1;
  return at / Math.max(left.length, right.length, 1);
}

export function normalised(text: string): string {
  return text.replace(/[0-9]+/g, "#").replace(/\s+/g, " ").trim();
}
