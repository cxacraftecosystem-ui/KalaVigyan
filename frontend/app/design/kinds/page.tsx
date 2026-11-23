import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { MonographPage } from "@/components/monograph/MonographPage";
import { KIND_PREVIEW_TITLE, kindPreviewDocument } from "@/lib/kindPreview";
import { serverKindFixtures } from "@/lib/server/kindFixturesServer";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: KIND_PREVIEW_TITLE,
  description: "Each component kind a contributor can deliver, drawn for a craft other than Kutch Ajrakh from that craft's stored facts.",
  robots: { index: false, follow: false }
};

export default async function KindPreviewPage() {
  const fixtures = await serverKindFixtures();
  if (fixtures === null) notFound();
  return <MonographPage document={kindPreviewDocument(fixtures)} />;
}
