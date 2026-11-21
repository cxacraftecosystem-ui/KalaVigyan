import type { DocumentLanguageCode } from "@/lib/documentLanguages";
import type { MonographDocument } from "@/lib/monographDocument";
import { serverDocumentInLanguage } from "@/lib/monographLanguagesServer";
import { prerenderedShells, serverCraftDocument, type ShellParams } from "@/lib/monographRenderServer";
import { documentDigest, restAddress, restBody, type RestAddress } from "@/lib/monographRenderShell";

type ShellRoute = { params: Promise<ShellParams> };

export const dynamic = "force-static";
export const revalidate = 86400;
export const dynamicParams = true;

export async function generateStaticParams(): Promise<ShellParams[]> {
  return prerenderedShells();
}

async function translated(slug: string, address: RestAddress, language: DocumentLanguageCode): Promise<MonographDocument | null> {
  const current = await serverDocumentInLanguage("craft", slug, language);
  const same = current !== null && current.version === address.version && documentDigest(current) === address.digest;
  const read = same ? current : await serverDocumentInLanguage("craft", slug, language, address.version);
  return read !== null && read.language === language ? read : null;
}

async function addressed(slug: string, address: RestAddress): Promise<MonographDocument | null> {
  if (address.language !== null) return translated(slug, address, address.language);
  const current = await serverCraftDocument(slug);
  const same = current !== null && current.version === address.version && (address.digest === null || documentDigest(current) === address.digest);
  return same ? current : serverCraftDocument(slug, address.version);
}

export async function GET(_request: Request, { params }: ShellRoute): Promise<Response> {
  const { slug, version } = await params;
  const address = restAddress(version);
  const document = address === null ? null : await addressed(slug, address);
  if (!document) return new Response(null, { status: 404 });
  return Response.json(restBody(document));
}
