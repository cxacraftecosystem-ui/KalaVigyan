import { craftEdition } from "@/lib/craftPageContract";
import { serverCraftDocument } from "@/lib/monographRenderServer";
import { shellRest } from "@/lib/monographRenderShell";

type ShellRoute = { params: Promise<{ slug: string; version: string }> };

export const dynamic = "force-static";
export const revalidate = 86400;
export const dynamicParams = true;

export async function generateStaticParams(): Promise<{ slug: string; version: string }[]> {
  return [];
}

export async function GET(_request: Request, { params }: ShellRoute): Promise<Response> {
  const { slug, version } = await params;
  const edition = craftEdition(version);
  const document = edition === null ? null : await serverCraftDocument(slug, edition);
  if (!document || document.shell === null) return new Response(null, { status: 404 });
  return Response.json(shellRest(document));
}
