import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { MonographPage } from "@/components/monograph/MonographPage";
import { craftEdition } from "@/lib/craftPageContract";
import { monographMetadata } from "@/lib/monographMetadata";
import { serverCraftDocument } from "@/lib/monographRenderServer";

type CraftEditionRoute = { params: Promise<{ slug: string; edition: string }> };

export const revalidate = 86400;
export const dynamicParams = true;

async function editionOf(params: CraftEditionRoute["params"]): Promise<{ slug: string; version: number }> {
  const { slug, edition } = await params;
  const version = craftEdition(edition);
  if (version === null) notFound();
  return { slug, version };
}

export async function generateMetadata({ params }: CraftEditionRoute): Promise<Metadata> {
  const { slug, version } = await editionOf(params);
  const document = await serverCraftDocument(slug, version);
  return document ? monographMetadata(document) : {};
}

export default async function CraftEditionPage({ params }: CraftEditionRoute) {
  const { slug, version } = await editionOf(params);
  const document = await serverCraftDocument(slug, version);
  if (!document) notFound();
  return <MonographPage document={document} deferred />;
}
