import type { Metadata } from "next";
import { cache } from "react";

import type { MonographDocument } from "@/lib/monographDocument";
import { monographDocumentPath, versionedDocumentPath, type MonographPreviewSubject } from "@/lib/monographDocumentShape";
import { parseNamedDocument } from "@/lib/monographRenderCitations";
import { prerenderedPages, STATIC_FETCH_TIMEOUT_MS } from "@/lib/server/readingPages";
import { publicFetch, type ServerFetchResult } from "@/lib/server/serverFetch";
import { STATIC_PAGE_REVALIDATE_SECONDS, type CraftParams } from "@/lib/sitePagesContract";

export const PREVIEW_ROBOTS = { index: false, follow: false } as const;
export const PREVIEW_TITLE = "Monograph";
export const DOCUMENT_UNAVAILABLE = "The monograph could not be read";
const NOT_FOUND = 404;

export async function previewStaticParams(subject: MonographPreviewSubject): Promise<CraftParams[]> {
  return prerenderedPages(subject === "craft" ? "crafts" : "categories");
}

export async function previewMetadata(subject: MonographPreviewSubject, slug: string): Promise<Metadata> {
  const document = await serverMonographDocument(subject, slug);
  return { title: document?.title ?? PREVIEW_TITLE, robots: PREVIEW_ROBOTS };
}

export const monographDocumentTag = (subject: MonographPreviewSubject, slug: string) => `monograph-document:${subject}:${slug}`;

export function documentOrAbsent<T>(result: ServerFetchResult<T>): T | null {
  if (result.ok) return result.body;
  if (result.status === NOT_FOUND) return null;
  throw new Error(`${DOCUMENT_UNAVAILABLE}: ${result.failure}`);
}

async function documentRead(path: string, tag: string): Promise<MonographDocument | null> {
  const result = await publicFetch(path, {
    parse: parseNamedDocument,
    tags: [tag],
    revalidateSeconds: STATIC_PAGE_REVALIDATE_SECONDS,
    deps: { timeoutMs: STATIC_FETCH_TIMEOUT_MS }
  });
  return documentOrAbsent(result);
}

export const serverMonographDocument = cache(async (subject: MonographPreviewSubject, slug: string): Promise<MonographDocument | null> =>
  documentRead(monographDocumentPath(subject, slug), monographDocumentTag(subject, slug))
);

export type ShellParams = { slug: string; version: string };

export function shellParams(documents: readonly (MonographDocument | null)[]): ShellParams[] {
  return documents.flatMap((document) => (document && document.shell !== null ? [{ slug: document.subjectSlug, version: `v${document.version}` }] : []));
}

export async function prerenderedShells(): Promise<ShellParams[]> {
  const crafts = await prerenderedPages("crafts");
  return shellParams(await Promise.all(crafts.map(({ slug }) => serverCraftDocument(slug))));
}

export const serverCraftDocument = cache(async (slug: string, version: number | null = null): Promise<MonographDocument | null> =>
  documentRead(versionedDocumentPath(monographDocumentPath("craft", slug), version), monographDocumentTag("craft", slug))
);
