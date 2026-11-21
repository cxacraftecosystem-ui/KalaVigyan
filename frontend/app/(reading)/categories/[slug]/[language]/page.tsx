import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { CategoryHub, hubDek } from "@/components/crafts/CategoryHub";
import { MonographPage } from "@/components/monograph/MonographPage";
import { familyName, findFamily } from "@/lib/atlasCollection";
import { documentLanguagePath, isDocumentLanguage, languageAlternates, pagePath } from "@/lib/documentLanguages";
import { serverDocumentInLanguage, serverPageLanguages } from "@/lib/monographLanguagesServer";
import { requiredCraftCatalogue } from "@/lib/server/readingPages";

type CategoryLanguageRoute = { params: Promise<{ slug: string; language: string }> };

export const revalidate = 86400;
export const dynamicParams = true;

async function asked(params: CategoryLanguageRoute["params"]) {
  const { slug, language } = await params;
  if (!isDocumentLanguage(language)) notFound();
  const catalogue = await requiredCraftCatalogue();
  const category = findFamily(catalogue, slug);
  if (!category) notFound();
  return { catalogue, category, language };
}

export async function generateMetadata({ params }: CategoryLanguageRoute): Promise<Metadata> {
  const { catalogue, category, language } = await asked(params);
  const title = familyName(category);
  const description = hubDek(catalogue, category);
  const url = documentLanguagePath("category", category.slug, language);
  const languages = await serverPageLanguages("category", category.slug);
  const alternates = languages ? languageAlternates("category", category.slug, languages.languages) : {};
  return { title, description, alternates: { canonical: url, languages: alternates }, openGraph: { title, description, type: "website", url } };
}

export default async function CategoryLanguagePage({ params }: CategoryLanguageRoute) {
  const { catalogue, category, language } = await asked(params);
  const document = await serverDocumentInLanguage("category", category.slug, language);
  if (!document || document.language !== language) redirect(pagePath("category", category.slug));
  const languages = await serverPageLanguages("category", category.slug);
  return <CategoryHub catalogue={catalogue} category={category} science={<MonographPage document={document} masthead={false} deferred languages={languages} />} />;
}
