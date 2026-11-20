import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { MonographPage } from "@/components/monograph/MonographPage";
import { previewMetadata, previewStaticParams, serverMonographDocument } from "@/lib/monographRenderServer";
import type { CraftParams } from "@/lib/sitePagesContract";

type CraftMonographRoute = { params: Promise<{ slug: string }> };

export const revalidate = 86400;
export const dynamicParams = true;

export async function generateStaticParams(): Promise<CraftParams[]> {
  return previewStaticParams("craft");
}

export async function generateMetadata({ params }: CraftMonographRoute): Promise<Metadata> {
  const { slug } = await params;
  return previewMetadata("craft", slug);
}

export default async function CraftMonographPreview({ params }: CraftMonographRoute) {
  const { slug } = await params;
  const document = await serverMonographDocument("craft", slug);
  if (!document) notFound();
  return <MonographPage document={document} deferred />;
}
