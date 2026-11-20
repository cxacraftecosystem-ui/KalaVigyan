import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CraftWithoutMonograph } from "@/components/craft/CraftWithoutMonograph";
import { MonographPage } from "@/components/monograph/MonographPage";
import { craftRecordView } from "@/lib/craftRecord";
import { monographMetadata } from "@/lib/monographMetadata";
import { serverCraftDocument } from "@/lib/monographRenderServer";
import { craftPageMetadata } from "@/lib/readingMetadata";
import { serverStaticPages } from "@/lib/server/readingPages";
import { staticCraftParams, type CraftParams } from "@/lib/sitePagesContract";

import { craftRecordPage } from "./craftRecordPage";

type CraftRoute = { params: Promise<{ slug: string }> };

export const revalidate = 86400;
export const dynamicParams = true;

export async function generateStaticParams(): Promise<CraftParams[]> {
  return staticCraftParams(await serverStaticPages());
}

export async function generateMetadata({ params }: CraftRoute): Promise<Metadata> {
  const { slug } = await params;
  const document = await serverCraftDocument(slug);
  if (document) return monographMetadata(document);
  return craftPageMetadata(await craftRecordPage(slug));
}

export default async function CraftPage({ params }: CraftRoute) {
  const { slug } = await params;
  const document = await serverCraftDocument(slug);
  if (document) return <MonographPage document={document} />;
  const page = await craftRecordPage(slug);
  if (!page) notFound();
  return <CraftWithoutMonograph record={craftRecordView(page)} />;
}
