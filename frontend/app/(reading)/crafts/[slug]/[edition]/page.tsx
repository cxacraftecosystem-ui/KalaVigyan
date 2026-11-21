import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { MonographPage } from "@/components/monograph/MonographPage";
import { craftEdition } from "@/lib/craftPageContract";
import { isDocumentLanguage, pagePath, type DocumentLanguageCode } from "@/lib/documentLanguages";
import type { MonographDocument } from "@/lib/monographDocument";
import { monographMetadata } from "@/lib/monographMetadata";
import { serverDocumentInLanguage, serverPageLanguages } from "@/lib/monographLanguagesServer";
import { serverCraftDocument } from "@/lib/monographRenderServer";

type CraftEditionRoute = { params: Promise<{ slug: string; edition: string }> };
type Edition = { slug: string; version: number | null; language: DocumentLanguageCode | null };

export const revalidate = 86400;
export const dynamicParams = true;

async function editionOf(params: CraftEditionRoute["params"]): Promise<Edition> {
  const { slug, edition } = await params;
  if (isDocumentLanguage(edition)) return { slug, version: null, language: edition };
  const version = craftEdition(edition);
  if (version === null) notFound();
  return { slug, version, language: null };
}

async function editionDocument(edition: Edition): Promise<MonographDocument | null> {
  if (edition.language === null) return serverCraftDocument(edition.slug, edition.version);
  return serverDocumentInLanguage("craft", edition.slug, edition.language);
}

export async function generateMetadata({ params }: CraftEditionRoute): Promise<Metadata> {
  const edition = await editionOf(params);
  const document = await editionDocument(edition);
  if (!document) return {};
  const languages = edition.language ? await serverPageLanguages(document.subjectKind, document.subjectSlug) : null;
  return monographMetadata(document, languages);
}

export default async function CraftEditionPage({ params }: CraftEditionRoute) {
  const edition = await editionOf(params);
  const document = await editionDocument(edition);
  if (!document) notFound();
  if (edition.language === null) return <MonographPage document={document} deferred />;
  if (document.language !== edition.language) redirect(pagePath(document.subjectKind, document.subjectSlug));
  const languages = await serverPageLanguages(document.subjectKind, document.subjectSlug);
  return <MonographPage document={document} deferred languages={languages} />;
}
