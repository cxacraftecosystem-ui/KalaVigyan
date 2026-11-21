import { cache } from "react";

import { documentLanguagesPath, parsePageLanguages, type DocumentLanguageCode, type PageKind, type PageLanguages } from "@/lib/documentLanguages";
import type { MonographDocument } from "@/lib/monographDocument";
import { monographDocumentPath, type MonographPreviewSubject } from "@/lib/monographDocumentShape";
import { documentRead, monographDocumentTag } from "@/lib/monographRenderServer";
import { STATIC_FETCH_TIMEOUT_MS } from "@/lib/server/readingPages";
import { publicFetch } from "@/lib/server/serverFetch";
import { STATIC_PAGE_REVALIDATE_SECONDS } from "@/lib/sitePagesContract";

const READ = { revalidateSeconds: STATIC_PAGE_REVALIDATE_SECONDS, deps: { timeoutMs: STATIC_FETCH_TIMEOUT_MS } };

function tagOf(kind: PageKind, slug: string): string {
  return monographDocumentTag(kind === "category" ? "category" : "craft", slug);
}

export const serverPageLanguages = cache(async (kind: PageKind, slug: string): Promise<PageLanguages | null> => {
  const result = await publicFetch(documentLanguagesPath(kind, slug), { parse: parsePageLanguages, tags: [tagOf(kind, slug)], ...READ });
  return result.ok ? result.body : null;
});

export const serverDocumentInLanguage = cache(
  async (subject: MonographPreviewSubject, slug: string, language: DocumentLanguageCode, version: number | null = null): Promise<MonographDocument | null> =>
    documentRead(monographDocumentPath(subject, slug), monographDocumentTag(subject, slug), { version, language, tag: null })
);
