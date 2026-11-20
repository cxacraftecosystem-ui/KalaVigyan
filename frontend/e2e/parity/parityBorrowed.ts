import type { APIRequestContext } from "@playwright/test";

import HOMES from "../../lib/componentHomes.json";

export type SubjectKind = "craft" | "family" | "category";
export type DocumentComponent = { label: string; kind: string };
export type SubjectPage = { path: string; slug: string; subject: SubjectKind; curated: boolean; authored: boolean; components: DocumentComponent[] };
export type BorrowedCase = { label: string; kind: string; page: SubjectPage; root: string | null; frame: number };
export type HomeEntry = { kind: string; scope: string | null; frame: { classes: string[]; box: boolean }[]; root: string | null; within?: string };

export const AUTHORED_PATH = "/crafts/Kutch-Ajrakh";
const PAGES_PATH = "/api/site/pages";
const STRUCTURE_KIND = "answer_block";
const FETCHES_AT_ONCE = 8;

const BOOK = HOMES as { homes: Record<string, HomeEntry> };

type DocumentBody = { subjectKind?: string; subjectSlug?: string; shell?: string | null; content?: { components?: DocumentComponent[] } };

export function homeOf(label: string): HomeEntry | null {
  return Object.hasOwn(BOOK.homes, label) ? BOOK.homes[label] : null;
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

async function documentOf(request: APIRequestContext, asked: "craft" | "category", slug: string): Promise<SubjectPage | null> {
  const path = asked === "category" ? `/api/categories/${encodeURIComponent(slug)}/monograph` : `/api/crafts/${encodeURIComponent(slug)}/monograph`;
  const response = await request.get(path, { failOnStatusCode: false, timeout: 60_000 });
  if (!response.ok()) return null;
  return subjectPage((await response.json()) as DocumentBody, asked, slug);
}

export async function subjectPages(request: APIRequestContext): Promise<SubjectPage[]> {
  const listed = (await (await request.get(PAGES_PATH, { timeout: 60_000 })).json()) as { crafts?: string[]; categories?: string[] };
  const asked: ["craft" | "category", string][] = [...(listed.categories ?? []).map((slug) => ["category", slug] as ["category", string]), ...(listed.crafts ?? []).map((slug) => ["craft", slug] as ["craft", string])];
  const found: SubjectPage[] = [];
  for (let at = 0; at < asked.length; at += FETCHES_AT_ONCE) {
    const batch = await Promise.all(asked.slice(at, at + FETCHES_AT_ONCE).map(([subject, slug]) => documentOf(request, subject, slug).catch(() => null)));
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
