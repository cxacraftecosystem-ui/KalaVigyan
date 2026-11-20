import { DISCIPLINES } from "@/lib/explainerBlockBase";

type Json = Record<string, unknown>;

export const MCP_PATH = "/api/mcp";
export const PROTOCOL_VERSION = "2025-11-25";
export const SERVER_NAME = "kalavigyan";
export const CHECKED_CRAFT = "Kutch-Ajrakh";
export const CHECKED_QUERY = "Ajrakh";
export const PUBLIC_TOOLS = ["find_crafts", "get_page", "get_facts", "list_components"] as const;
export const SCOPED_TOOL = "propose_facts";
export const PKCE_METHOD = "S256";
export const STANDINGS = { COVERED: "covered", THIN: "thin", MISSING: "missing" } as const;

const FOUND_MAX = 5;

function record(value: unknown): Json | null {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Json) : null;
}

function records(value: unknown): Json[] | null {
  return Array.isArray(value) && value.every((item) => record(item) !== null) ? (value as Json[]) : null;
}

export function replyResult(reply: unknown): { result: Json | null; problems: string[] } {
  const message = record(reply);
  if (!message) return { result: null, problems: ["the reply is not a JSON-RPC message"] };
  const failure = record(message.error);
  if (failure) return { result: null, problems: [`the server answered error ${String(failure.code)}: ${String(failure.message)}`] };
  const result = record(message.result);
  const problems = message.jsonrpc === "2.0" ? [] : ["the reply does not name JSON-RPC 2.0"];
  return result ? { result, problems } : { result: null, problems: [...problems, "the reply carries no result"] };
}

export function initializeProblems(result: Json): string[] {
  const problems: string[] = [];
  if (result.protocolVersion !== PROTOCOL_VERSION) problems.push(`initialize agreed ${String(result.protocolVersion)}; it should agree ${PROTOCOL_VERSION}`);
  if (record(result.serverInfo)?.name !== SERVER_NAME) problems.push(`the server names itself ${String(record(result.serverInfo)?.name)}; it should be ${SERVER_NAME}`);
  if (!record(result.capabilities)?.tools) problems.push("the server does not offer tools in its capabilities");
  return problems;
}

export function toolListProblems(result: Json): string[] {
  const tools = records(result.tools);
  if (!tools) return ["tools/list carries no list of tools"];
  const names = tools.map((tool) => String(tool.name));
  const problems = PUBLIC_TOOLS.filter((name) => !names.includes(name)).map((name) => `tools/list does not offer ${name}`);
  const twice = names.filter((name, at) => names.indexOf(name) !== at);
  if (twice.length) problems.push(`tools/list offers ${[...new Set(twice)].join(", ")} twice`);
  for (const tool of tools) {
    if (record(tool.inputSchema)?.type !== "object") problems.push(`${String(tool.name)} has no object input schema`);
    if (typeof tool.description !== "string" || !tool.description.trim()) problems.push(`${String(tool.name)} has no description`);
  }
  return problems;
}

export function toolContent(result: Json): { content: Json | null; problems: string[] } {
  if (result.isError === true) {
    const first = records(result.content)?.[0];
    return { content: null, problems: [`the tool answered an error: ${String(first?.text ?? "no text")}`] };
  }
  const content = record(result.structuredContent);
  return content ? { content, problems: [] } : { content: null, problems: ["the tool result carries no structured content"] };
}

function slugOf(value: unknown): string | null {
  const slug = record(value)?.slug;
  return typeof slug === "string" ? slug : null;
}

export function foundCraftsProblems(found: Json, slug: string): string[] {
  const crafts = records(found.crafts);
  if (found.schemaVersion !== 1) return [`find_crafts answers schema ${String(found.schemaVersion)}; the contract is schema 1`];
  if (!crafts || crafts.length === 0) return ["find_crafts found no craft"];
  const problems: string[] = [];
  if (crafts.length > FOUND_MAX) problems.push(`find_crafts answered ${crafts.length} crafts; it answers at most ${FOUND_MAX}`);
  if (!crafts.some((item) => slugOf(item.craft) === slug)) problems.push(`find_crafts did not find ${slug}`);
  const unlinked = crafts.filter((item) => typeof item.pageUrl !== "string" || !/^https:\/\//.test(item.pageUrl));
  if (unlinked.length) problems.push(`${unlinked.length} found crafts carry no https page link`);
  return problems;
}

function citationProblems(facts: Json[], sources: Json[]): string[] {
  const listed = new Set(sources.map((source) => String(source.id)));
  const uncited = facts.filter((fact) => (records(fact.citations) ?? []).length === 0);
  const strays = facts.flatMap((fact) => (records(fact.citations) ?? []).map((citation) => String(citation.sourceId))).filter((id) => !listed.has(id));
  const problems = uncited.length ? [`${uncited.length} facts carry no citation`] : [];
  if (strays.length) problems.push(`facts cite ${[...new Set(strays)].join(", ")}, which the answer does not list among its sources`);
  return problems;
}

export function craftFactsProblems(answer: Json, slug: string): string[] {
  if (slugOf(answer.craft) !== slug) return [`get_facts answered for ${String(slugOf(answer.craft))}; it was asked for ${slug}`];
  const facts = records(answer.facts);
  const sources = records(answer.sources);
  if (!facts || facts.length === 0) return [`get_facts holds no fact for ${slug}`];
  const problems = sources ? citationProblems(facts, sources) : ["get_facts lists no sources"];
  if (typeof answer.pageUrl !== "string" || !answer.pageUrl.startsWith("https://")) problems.push("get_facts carries no https page link");
  if (typeof answer.attribution !== "string" || !answer.attribution.trim()) problems.push("get_facts carries no attribution");
  return problems;
}

function standingProblems(coverage: Json, counts: Json[]): string[] {
  const problems: string[] = [];
  for (const [standing, list] of Object.entries(STANDINGS)) {
    const expected = counts.filter((count) => count.standing === standing).map((count) => String(count.field));
    const listed = Array.isArray(coverage[list]) ? (coverage[list] as unknown[]).map(String) : null;
    if (!listed || listed.join() !== expected.join()) problems.push(`the ${list} fields are [${listed?.join(", ") ?? "absent"}]; the field counts say [${expected.join(", ")}]`);
  }
  return problems;
}

export function coverageProblems(answer: Json, slug: string): string[] {
  const coverage = record(answer.coverage);
  if (!coverage) return ["get_page carries no coverage"];
  if (coverage.subjectSlug !== slug || coverage.subjectKind !== "craft") return [`get_page answered for ${String(coverage.subjectKind)} ${String(coverage.subjectSlug)}; it was asked for craft ${slug}`];
  const counts = records(coverage.fields) ?? [];
  const order = counts.map((count) => String(count.field));
  if (order.join() !== DISCIPLINES.join()) return [`get_page lists the fields [${order.join(", ")}]; it should list the ${DISCIPLINES.length} fields in order`];
  const problems = standingProblems(coverage, counts);
  if (typeof coverage.claims !== "number" || coverage.claims <= 0) problems.push(`get_page counts ${String(coverage.claims)} cited claims for a curated craft`);
  if (!Array.isArray(answer.openWork)) problems.push("get_page carries no open work list");
  return problems;
}

export function metadataProblems(resource: Json, server: Json, origins: { api: string; web: string }): string[] {
  const problems: string[] = [];
  const same = (what: string, actual: unknown, wanted: string) => {
    if (actual !== wanted) problems.push(`${what} is ${String(actual)}; it should be ${wanted}`);
  };
  same("the protected resource", resource.resource, `${origins.api}${MCP_PATH}`);
  if (!Array.isArray(resource.authorization_servers) || !resource.authorization_servers.includes(origins.api)) problems.push(`the protected resource does not name ${origins.api} as its authorization server`);
  same("the issuer", server.issuer, origins.api);
  same("the authorization endpoint", server.authorization_endpoint, `${origins.web}/oauth/authorize`);
  same("the token endpoint", server.token_endpoint, `${origins.api}/api/oauth/token`);
  same("the registration endpoint", server.registration_endpoint, `${origins.api}/api/oauth/register`);
  if (!Array.isArray(server.code_challenge_methods_supported) || !server.code_challenge_methods_supported.includes(PKCE_METHOD)) problems.push(`the authorization server does not offer PKCE ${PKCE_METHOD}`);
  return problems;
}
