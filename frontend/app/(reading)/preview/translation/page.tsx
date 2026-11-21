import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { MonographPage } from "@/components/monograph/MonographPage";
import { TEXT_SCRIPTS } from "@/lib/documentLanguages";
import { draftVariant } from "@/lib/documentVariant";
import { PREVIEW_ROBOTS, serverCraftDocument } from "@/lib/monographRenderServer";
import { previewLanguages, TRANSLATION_PREVIEW_LANGUAGE, TRANSLATION_PREVIEW_PASSAGES, TRANSLATION_PREVIEW_SLUG, TRANSLATION_PREVIEW_TITLE } from "@/lib/translationPreview";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: TRANSLATION_PREVIEW_TITLE, robots: PREVIEW_ROBOTS };

export default async function TranslationPreviewPage() {
  const english = await serverCraftDocument(TRANSLATION_PREVIEW_SLUG);
  if (!english) notFound();
  const document = draftVariant(english, TRANSLATION_PREVIEW_LANGUAGE, TEXT_SCRIPTS[TRANSLATION_PREVIEW_LANGUAGE], TRANSLATION_PREVIEW_PASSAGES);
  return <MonographPage document={document} languages={previewLanguages(document)} />;
}
