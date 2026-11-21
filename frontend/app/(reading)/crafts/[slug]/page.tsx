import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { notFound } from "next/navigation";

import { craftRecordView } from "@/lib/craftRecord";
import { monographMetadata } from "@/lib/monographMetadata";
import { serverCraftDocument } from "@/lib/monographRenderServer";
import { craftPageMetadata } from "@/lib/readingMetadata";
import { prerenderedPages } from "@/lib/server/readingPages";
import type { CraftParams } from "@/lib/sitePagesContract";

import { craftRecordPage } from "./craftRecordPage";

const MonographShellPage = dynamic(() => import("@/components/monograph/MonographShellPage").then((page) => page.MonographShellPage));
const MonographDocumentPage = dynamic(() => import("@/components/monograph/MonographDocumentPage").then((page) => page.MonographDocumentPage));
const CraftWithoutMonograph = dynamic(() => import("@/components/craft/CraftWithoutMonograph").then((page) => page.CraftWithoutMonograph));

type CraftRoute = { params: Promise<{ slug: string }> };

export const revalidate = 86400;
export const dynamicParams = true;

export async function generateStaticParams(): Promise<CraftParams[]> {
  return prerenderedPages("crafts");
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
  if (document) return document.shell !== null ? <MonographShellPage document={document} deferred /> : <MonographDocumentPage document={document} deferred />;
  const page = await craftRecordPage(slug);
  if (!page) notFound();
  return <CraftWithoutMonograph record={craftRecordView(page)} />;
}
