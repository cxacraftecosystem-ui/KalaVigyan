import { prerenderedShells, serverCraftDocument, type ShellParams } from "@/lib/monographRenderServer";
import { restAddress, restBody } from "@/lib/monographRenderShell";

type ShellRoute = { params: Promise<ShellParams> };

export const dynamic = "force-static";
export const revalidate = 86400;
export const dynamicParams = true;

export async function generateStaticParams(): Promise<ShellParams[]> {
  return prerenderedShells();
}

export async function GET(_request: Request, { params }: ShellRoute): Promise<Response> {
  const { slug, version } = await params;
  const edition = restAddress(version)?.version ?? null;
  const document = edition === null ? null : await serverCraftDocument(slug, edition);
  if (!document) return new Response(null, { status: 404 });
  return Response.json(restBody(document));
}
