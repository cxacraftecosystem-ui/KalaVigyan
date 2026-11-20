import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { MonographPage } from "@/components/monograph/MonographPage";
import { PREVIEW_ROBOTS } from "@/lib/monographRenderServer";
import { signInHref } from "@/lib/sessionReturn";

import { previewDocument, previewPagePath } from "./previewDocument";

type PreviewRoute = { params: Promise<{ token: string }> };

const PREVIEW_TITLE = "Preview";

export async function generateMetadata({ params }: PreviewRoute): Promise<Metadata> {
  const { token } = await params;
  const found = await previewDocument(token);
  const title = found.kind === "shown" ? `${PREVIEW_TITLE}: ${found.document.title}` : PREVIEW_TITLE;
  return { title, robots: PREVIEW_ROBOTS };
}

export default async function PagePreview({ params }: PreviewRoute) {
  const { token } = await params;
  const found = await previewDocument(token);
  if (found.kind === "signed-out") redirect(signInHref(previewPagePath(token)));
  if (found.kind === "missing") notFound();
  return <MonographPage document={found.document} />;
}
