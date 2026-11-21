import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CategoryHub, hubDek } from "@/components/crafts/CategoryHub";
import { MonographPage } from "@/components/monograph/MonographPage";
import { familyName, findFamily } from "@/lib/atlasCollection";
import { languageAlternates } from "@/lib/documentLanguages";
import { serverPageLanguages } from "@/lib/monographLanguagesServer";
import { previewStaticParams, serverMonographDocument } from "@/lib/monographRenderServer";
import { requiredCraftCatalogue } from "@/lib/server/readingPages";
import type { CraftParams } from "@/lib/sitePagesContract";

type CategoryRoute = { params: Promise<{ slug: string }> };

export const revalidate = 86400;
export const dynamicParams = true;

export async function generateStaticParams(): Promise<CraftParams[]> {
  return previewStaticParams("category");
}

export async function generateMetadata({ params }: CategoryRoute): Promise<Metadata> {
  const { slug } = await params;
  const catalogue = await requiredCraftCatalogue();
  const category = findFamily(catalogue, slug);
  if (!category) return {};
  const title = familyName(category);
  const description = hubDek(catalogue, category);
  const languages = await serverPageLanguages("category", category.slug);
  const alternates = languages ? languageAlternates("category", category.slug, languages.languages) : {};
  const linked = Object.keys(alternates).length ? { alternates: { languages: alternates } } : {};
  return { title, description, ...linked, openGraph: { title, description, type: "website", url: `/categories/${category.slug}` } };
}

export default async function CategoryPage({ params }: CategoryRoute) {
  const { slug } = await params;
  const catalogue = await requiredCraftCatalogue();
  const category = findFamily(catalogue, slug);
  if (!category) notFound();
  const document = await serverMonographDocument("category", category.slug);
  const languages = document ? await serverPageLanguages("category", category.slug) : null;
  return <CategoryHub catalogue={catalogue} category={category} science={document ? <MonographPage document={document} masthead={false} deferred languages={languages} /> : null} />;
}
