import { craftEdition } from "@/lib/craftPageContract";
import { serverMonographDocument, type ShellParams } from "@/lib/monographRenderServer";
import { documentRest } from "@/lib/monographRenderShell";

type RestRoute = { params: Promise<ShellParams> };

export const dynamic = "force-static";
export const revalidate = 86400;
export const dynamicParams = true;

export async function generateStaticParams(): Promise<ShellParams[]> {
  return [];
}

export async function GET(_request: Request, { params }: RestRoute): Promise<Response> {
  const { slug, version } = await params;
  const edition = craftEdition(version);
  const document = edition === null ? null : await serverMonographDocument("category", slug);
  if (!document || document.version !== edition || document.shell !== null) return new Response(null, { status: 404 });
  return Response.json(documentRest(document));
}
