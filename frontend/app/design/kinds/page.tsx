import type { Metadata } from "next";

import { MonographPage } from "@/components/monograph/MonographPage";
import { KIND_FIXTURES } from "@/lib/kindFixtures";
import { KIND_PREVIEW_TITLE, kindPreviewDocument } from "@/lib/kindPreview";

export const metadata: Metadata = {
  title: KIND_PREVIEW_TITLE,
  description: "Each component kind a contributor can deliver, drawn for a craft other than Kutch Ajrakh from that craft's stored facts.",
  robots: { index: false, follow: false }
};

export default function KindPreviewPage() {
  return <MonographPage document={kindPreviewDocument(KIND_FIXTURES)} />;
}
