import type { Metadata } from "next";

import { commonsThumb, isCommonsFile } from "@/lib/commonsPicture";
import { documentLanguagePath, languageAlternates, type PageLanguages } from "@/lib/documentLanguages";
import { ENGLISH, type MonographDocument } from "@/lib/monographDocument";
import { mastheadPhoto } from "@/lib/monographMasthead";
import { nodesText } from "@/lib/monographRender";
import { pagePlan } from "@/lib/monographRenderLayout";

export const SHARED_PICTURE_WIDTH = 1280;
export const CRAFT_READING_PATH = (slug: string) => `/crafts/${slug}`;

export type SharedPicture = { url: string; width: number; alt: string };

export function documentDescription(document: MonographDocument): string | undefined {
  const plan = pagePlan(document);
  const refs = plan.label ? plan.label.lede : [plan.masthead.lede].filter((ref): ref is string => ref !== null);
  const text = refs.map((ref) => nodesText(document.content.units[ref]?.nodes ?? []).trim()).filter(Boolean).join(" ");
  return text || undefined;
}

export function documentPicture(document: MonographDocument): SharedPicture | null {
  const plan = pagePlan(document);
  const photo = mastheadPhoto(document, plan.label?.picture ?? null);
  if (!photo || !isCommonsFile(photo.src)) return null;
  return { url: commonsThumb(photo.src, SHARED_PICTURE_WIDTH), width: SHARED_PICTURE_WIDTH, alt: [photo.caption, photo.credit].filter(Boolean).join(" · ") };
}

export function monographMetadata(document: MonographDocument, languages: PageLanguages | null = null): Metadata {
  const path = document.language === ENGLISH ? CRAFT_READING_PATH(document.subjectSlug) : documentLanguagePath(document.subjectKind, document.subjectSlug, document.language);
  const description = documentDescription(document);
  const picture = documentPicture(document);
  const alternates = languages ? languageAlternates(document.subjectKind, document.subjectSlug, languages.languages) : {};
  return {
    title: document.title,
    description,
    alternates: Object.keys(alternates).length ? { canonical: path, languages: alternates } : { canonical: path },
    openGraph: { title: document.title, description, type: "article", url: path, images: picture ? [picture] : [] },
    twitter: { card: picture ? "summary_large_image" : "summary", title: document.title, description }
  };
}
