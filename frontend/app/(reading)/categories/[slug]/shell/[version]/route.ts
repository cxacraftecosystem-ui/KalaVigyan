import { ENGLISH, type MonographDocument } from "@/lib/monographDocument";
import { serverDocumentInLanguage } from "@/lib/monographLanguagesServer";
import { serverMonographDocument, type ShellParams } from "@/lib/monographRenderServer";
import { documentRest, restAddress, type RestAddress } from "@/lib/monographRenderShell";

type RestRoute = { params: Promise<ShellParams> };

export const dynamic = "force-static";
export const revalidate = 86400;
export const dynamicParams = true;

export async function generateStaticParams(): Promise<ShellParams[]> {
  return [];
}

async function addressed(slug: string, address: RestAddress): Promise<MonographDocument | null> {
  const document = address.language === null ? await serverMonographDocument("category", slug) : await serverDocumentInLanguage("category", slug, address.language);
  const same = document !== null && document.version === address.version && document.shell === null && document.language === (address.language ?? ENGLISH);
  return same ? document : null;
}

export async function GET(_request: Request, { params }: RestRoute): Promise<Response> {
  const { slug, version } = await params;
  const address = restAddress(version);
  const document = address === null ? null : await addressed(slug, address);
  if (!document) return new Response(null, { status: 404 });
  return Response.json(documentRest(document));
}
