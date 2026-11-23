import type { Metadata } from "next";

import { commonsThumb, isCommonsFile } from "@/lib/commonsPicture";
import type { CraftCatalogue } from "@/lib/craftCatalogueContract";
import type { CraftPage, PagePlate } from "@/lib/craftPageContract";
import { craftSubtitle } from "@/lib/craftPageView";
import { photoCredit } from "@/lib/editorialText";

export const SHARE_PICTURE_WIDTH = 1280;
export const ATLAS_TITLE = "Crafts";

type SharedPicture = { url: string; width: number; alt: string };

export function craftPageMetadata(page: CraftPage | null): Metadata {
  if (!page) return {};
  const description = page.lede[0]?.text ?? craftSubtitle(page.craft);
  const picture = sharedPicture(page.masthead.picture);
  return {
    title: page.craft.name,
    description,
    alternates: { canonical: page.craft.path },
    openGraph: { title: page.craft.name, description, type: "article", url: page.craft.path, images: picture ? [picture] : [] },
    twitter: { card: picture ? "summary_large_image" : "summary", title: page.craft.name, description }
  };
}

export function atlasMetadata(catalogue: CraftCatalogue | null): Metadata {
  const crafts = catalogue?.summary.crafts ?? null;
  const description = crafts ? `${crafts.toLocaleString("en-IN")} Indian crafts, with the science behind each one, every sentence cited.` : undefined;
  return { title: ATLAS_TITLE, description, openGraph: { title: ATLAS_TITLE, description, type: "website", url: "/crafts" } };
}

export function sharedPicture(picture: Pick<PagePlate, "media" | "caption"> | null): SharedPicture | null {
  if (!picture || !isCommonsFile(picture.media.imageUrl)) return null;
  const { author, licence } = picture.media;
  const credit = author && licence ? photoCredit(author, licence) : picture.media.credit;
  return {
    url: commonsThumb(picture.media.imageUrl, SHARE_PICTURE_WIDTH),
    width: SHARE_PICTURE_WIDTH,
    alt: [picture.caption, credit].filter(Boolean).join(". ")
  };
}
