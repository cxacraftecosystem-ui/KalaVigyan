import { CATALOGUE_METHODS, MCP_PROTOCOL_VERSION, MCP_ROUTE, RESOURCE_METADATA_PATH, catalogueOf, catalogueRequest, resourceOf, type ConnectFacts, type McpCatalogue } from "@/lib/connectCatalogue";
import { apiOrigin } from "@/lib/server/apiProxy";

export const MCP_GUIDE_REVALIDATE_SECONDS = 300;
export const MCP_GUIDE_TIMEOUT_MS = 4_000;

type Env = Record<string, string | undefined>;
export type GuideDeps = { fetcher: typeof fetch; env: Env };

const DEFAULT_DEPS: GuideDeps = { fetcher: (...args) => fetch(...args), env: process.env as Env };

async function readJson(deps: GuideDeps, url: string, init: RequestInit): Promise<unknown> {
  const response = await deps.fetcher(url, { ...init, redirect: "manual", signal: AbortSignal.timeout(MCP_GUIDE_TIMEOUT_MS), next: { revalidate: MCP_GUIDE_REVALIDATE_SECONDS } });
  if (!response.ok) throw new Error(`${url} answered ${response.status}`);
  return response.json();
}

function listCall(deps: GuideDeps, origin: string, method: (typeof CATALOGUE_METHODS)[number], id: number): Promise<unknown> {
  return readJson(deps, `${origin}${MCP_ROUTE}`, {
    method: "POST",
    headers: { accept: "application/json", "content-type": "application/json", "mcp-protocol-version": MCP_PROTOCOL_VERSION },
    body: catalogueRequest(method, id)
  });
}

export async function serverAddress(deps: GuideDeps = DEFAULT_DEPS): Promise<string | null> {
  const origin = apiOrigin(deps.env);
  if (!origin) return null;
  try {
    return resourceOf(await readJson(deps, `${origin}${RESOURCE_METADATA_PATH}`, { headers: { accept: "application/json" } }));
  } catch (error) {
    console.error("the MCP server's address could not be read", error);
    return null;
  }
}

export async function serverCatalogue(deps: GuideDeps = DEFAULT_DEPS): Promise<McpCatalogue | null> {
  const origin = apiOrigin(deps.env);
  if (!origin) return null;
  try {
    const [tools, prompts] = await Promise.all(CATALOGUE_METHODS.map((method, at) => listCall(deps, origin, method, at + 1)));
    return catalogueOf(tools, prompts);
  } catch (error) {
    console.error("the MCP server's tools could not be read", error);
    return null;
  }
}

export async function connectFacts(deps: GuideDeps = DEFAULT_DEPS): Promise<ConnectFacts> {
  const [address, catalogue] = await Promise.all([serverAddress(deps), serverCatalogue(deps)]);
  return { address, catalogue };
}
