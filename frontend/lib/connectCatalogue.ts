export const MCP_ROUTE = "/api/mcp";
export const MCP_PROTOCOL_VERSION = "2025-11-25";
export const RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource/api/mcp";
export const CATALOGUE_METHODS = ["tools/list", "prompts/list"] as const;

export type CatalogueMethod = (typeof CATALOGUE_METHODS)[number];

export type McpTool = { name: string; title: string; summary: string; writes: boolean };
export type McpPromptArgument = { name: string; description: string; required: boolean };
export type McpPrompt = { name: string; title: string; description: string; arguments: McpPromptArgument[] };
export type McpCatalogue = { tools: McpTool[]; prompts: McpPrompt[] };
export type ConnectFacts = { address: string | null; catalogue: McpCatalogue | null };

export type ToolGroupKey = "reading" | "asking" | "sources" | "work" | "proposing" | "components" | "pictures" | "drafts";
export type ToolGroup = { key: ToolGroupKey; title: string; about: string; tools: McpTool[] };

type Json = Record<string, unknown>;

export const TOOL_GROUPS: readonly Omit<ToolGroup, "tools">[] = [
  { key: "reading", title: "Reading", about: "Crafts, their sixteen fields, facts with their quotes, sections and coverage, as anyone reads them." },
  { key: "asking", title: "Asking", about: "Cited answers in your name, as the site gives them." },
  { key: "sources", title: "Finding and reading sources", about: "The registries, reader and quote matcher the checks themselves use." },
  { key: "work", title: "Open work", about: "Tasks to claim and give back, your own tasks and the crafts you steward." },
  { key: "proposing", title: "Proposing facts and structure", about: "Facts, new sources and a page's structure, each checked as on the site, and how each proposal is doing." },
  { key: "components", title: "Components and pages", about: "The component library, page layouts and whole page bundles." },
  { key: "pictures", title: "Pictures", about: "Open pictures to place and pictures you give." },
  { key: "drafts", title: "Drafts and previews", about: "A page assembled privately, seen before you submit it." }
];

const GROUP_RULES: readonly { key: ToolGroupKey; pattern: RegExp }[] = [
  { key: "pictures", pattern: /image|picture/ },
  { key: "drafts", pattern: /draft|preview/ },
  { key: "components", pattern: /component|layout|page/ },
  { key: "proposing", pattern: /^propose_|proposal|withdraw/ },
  { key: "sources", pattern: /source|quote|lookup|archive/ },
  { key: "work", pattern: /task|work|adopt|drop_|steward|my_crafts/ },
  { key: "asking", pattern: /^ask/ }
];

const SENTENCE = /^(.+?[.!?])(?=\s+[A-Z(“"'`]|$)/;

const CLAUSE_END = /[:;]\s/;
const ENDS_A_SENTENCE = /[.!?]$/;

export function firstSentence(text: string): string {
  const flat = text.trim().replace(/\s+/g, " ");
  return SENTENCE.exec(flat)?.[1] ?? flat;
}

export function toolSummary(description: string): string {
  const clause = firstSentence(description).split(CLAUSE_END)[0].replace(/,$/, "").trim();
  return ENDS_A_SENTENCE.test(clause) ? clause : `${clause}.`;
}

export function toolGroupOf(tool: Pick<McpTool, "name" | "writes">): ToolGroupKey {
  const rule = GROUP_RULES.find((candidate) => candidate.pattern.test(tool.name));
  if (rule) return rule.key;
  return tool.writes ? "proposing" : "reading";
}

export function groupTools(tools: readonly McpTool[]): ToolGroup[] {
  return TOOL_GROUPS.map((group) => ({ ...group, tools: tools.filter((tool) => toolGroupOf(tool) === group.key) })).filter((group) => group.tools.length > 0);
}

export function catalogueRequest(method: CatalogueMethod, id: number): string {
  return JSON.stringify({ jsonrpc: "2.0", id, method });
}

function record(value: unknown, what: string): Json {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error(`${what} is not an object`);
  return value as Json;
}

function words(value: unknown, what: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${what} is not a text`);
  return value.trim();
}

function entries(reply: unknown, key: "tools" | "prompts"): Json[] {
  const message = record(reply, `the ${key} reply`);
  if (message.error !== undefined) throw new Error(`the server refused ${key}/list`);
  const listed = record(message.result, `the ${key} result`)[key];
  if (!Array.isArray(listed)) throw new Error(`the ${key} result carries no list`);
  return listed.map((entry, at) => record(entry, `${key}[${at}]`));
}

function toolOf(entry: Json): McpTool {
  const name = words(entry.name, "a tool's name");
  const title = typeof entry.title === "string" && entry.title.trim() ? entry.title.trim() : name;
  const annotations = typeof entry.annotations === "object" && entry.annotations !== null ? (entry.annotations as Json) : {};
  return { name, title, summary: toolSummary(words(entry.description, `${name}'s description`)), writes: annotations.readOnlyHint !== true };
}

function argumentOf(entry: unknown, prompt: string): McpPromptArgument {
  const argument = record(entry, `an argument of ${prompt}`);
  const name = words(argument.name, `an argument name of ${prompt}`);
  const description = typeof argument.description === "string" ? argument.description.trim() : "";
  return { name, description, required: argument.required === true };
}

function promptOf(entry: Json): McpPrompt {
  const name = words(entry.name, "a prompt's name");
  const title = typeof entry.title === "string" && entry.title.trim() ? entry.title.trim() : name;
  const listed = Array.isArray(entry.arguments) ? entry.arguments : [];
  return { name, title, description: words(entry.description, `${name}'s description`), arguments: listed.map((argument) => argumentOf(argument, name)) };
}

export function catalogueOf(toolsReply: unknown, promptsReply: unknown): McpCatalogue {
  return { tools: entries(toolsReply, "tools").map(toolOf), prompts: entries(promptsReply, "prompts").map(promptOf) };
}

export function resourceOf(metadata: unknown): string {
  const resource = words(record(metadata, "the protected resource metadata").resource, "the resource");
  const url = new URL(resource);
  const loopback = url.hostname === "localhost" || url.hostname === "127.0.0.1";
  if (url.protocol !== "https:" && !(url.protocol === "http:" && loopback)) throw new Error(`the resource ${resource} is not an https address`);
  return resource;
}
