import { craftEdition } from "@/lib/craftPageContract";
import { prerenderedShells, serverCraftDocument, type ShellParams } from "@/lib/monographRenderServer";
import { shellRest } from "@/lib/monographRenderShell";

type ShellRoute = { params: Promise<ShellParams> };

export const dynamic = "force-static";
export const revalidate = 86400;
export const dynamicParams = true;

export async function generateStaticParams(): Promise<ShellParams[]> {
  return prerenderedShells();
}

export async function GET(_request: Request, { params }: ShellRoute): Promise<Response> {
  const { slug, version } = await params;
  const edition = craftEdition(version);
  const document = edition === null ? null : await serverCraftDocument(slug, edition);
  if (!document || document.shell === null) return new Response(null, { status: 404 });
  return Response.json(shellRest(document));
}
