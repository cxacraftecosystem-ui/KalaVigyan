import { apiFetch } from "@/lib/api";
import { CATALOGUE_METHODS, MCP_PROTOCOL_VERSION, MCP_ROUTE, catalogueOf, catalogueRequest, type CatalogueMethod, type McpCatalogue } from "@/lib/connectCatalogue";
import { fetchConnections } from "@/lib/oauthContract";

const SITE_MCP_PATH = MCP_ROUTE.replace(/^\/api/, "");

function listThroughSite(method: CatalogueMethod, id: number): Promise<unknown> {
  return apiFetch<unknown>(
    SITE_MCP_PATH,
    { method: "POST", headers: { accept: "application/json", "mcp-protocol-version": MCP_PROTOCOL_VERSION }, body: catalogueRequest(method, id) },
    { redirectOn401: false }
  );
}

export async function catalogueThroughSite(): Promise<McpCatalogue> {
  const [tools, prompts] = await Promise.all(CATALOGUE_METHODS.map((method, at) => listThroughSite(method, at + 1)));
  return catalogueOf(tools, prompts);
}

export async function addressThroughSite(): Promise<string> {
  const { serverUrl } = await fetchConnections();
  if (!serverUrl) throw new Error("the MCP server is switched off");
  return serverUrl;
}
