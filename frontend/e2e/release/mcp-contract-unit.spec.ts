import { expect, test } from "@playwright/test";

import { challengeParameters, challengeProblems } from "./mcpChallenge";
import { coverageProblems, craftFactsProblems, foundCraftsProblems, initializeProblems, metadataProblems, replyResult, toolContent, toolListProblems } from "./mcpContract";

const API = "https://api.example";
const WEB = "https://web.example";
const FIELDS = ["OVERVIEW", "PROCESS", "CHEMISTRY", "PHYSICS", "MATERIALS", "GEOGRAPHY", "GEOLOGY", "CLIMATE", "ECOLOGY", "BOTANY", "HISTORY", "ECONOMICS", "DESIGN", "HEALTH", "SOCIETY", "POLICY"];
const LISTED = ["find_crafts", "get_page", "get_facts", "list_components", "propose_facts"];

function tool(name: string) {
  return { name, description: `What ${name} does.`, inputSchema: { type: "object", properties: {} } };
}

function found(slugs: string[]) {
  return { schemaVersion: 1, query: "Ajrakh", crafts: slugs.map((slug) => ({ craft: { slug }, score: 0.9, pageUrl: `${WEB}/crafts/${slug}` })) };
}

function facts(citedSources: string[], listedSources: string[]) {
  return {
    schemaVersion: 1,
    craft: { slug: "Kutch-Ajrakh" },
    facts: citedSources.map((sourceId, at) => ({ id: `fact-${at}`, text: "Alum is the mordant.", citations: [{ sourceId, quote: "alum", locator: "p. 4" }] })),
    sources: listedSources.map((id) => ({ id })),
    pageUrl: `${WEB}/crafts/Kutch-Ajrakh`,
    attribution: "KalaVigyan"
  };
}

function coverage(thinFields: string[], missingFields: string[]) {
  const standing = (field: string) => (missingFields.includes(field) ? "MISSING" : thinFields.includes(field) ? "THIN" : "COVERED");
  return {
    coverage: {
      subjectKind: "craft",
      subjectSlug: "Kutch-Ajrakh",
      claims: 120,
      fields: FIELDS.map((field) => ({ field, standing: standing(field) })),
      covered: FIELDS.filter((field) => standing(field) === "COVERED"),
      thin: FIELDS.filter((field) => standing(field) === "THIN"),
      missing: FIELDS.filter((field) => standing(field) === "MISSING")
    },
    openWork: []
  };
}

test("a JSON-RPC error reply is named with its code and message", () => {
  expect(replyResult({ jsonrpc: "2.0", id: 1, error: { code: -32601, message: "no such method" } })).toEqual({ result: null, problems: ["the server answered error -32601: no such method"] });
  expect(replyResult({ jsonrpc: "2.0", id: 1, result: { tools: [] } }).problems).toEqual([]);
  expect(replyResult("<html>").problems).toEqual(["the reply is not a JSON-RPC message"]);
});

test("initialize must agree the 2025-11-25 protocol, name kalavigyan and offer tools", () => {
  expect(initializeProblems({ protocolVersion: "2025-11-25", serverInfo: { name: "kalavigyan" }, capabilities: { tools: {} } })).toEqual([]);
  expect(initializeProblems({ protocolVersion: "2025-03-26", serverInfo: { name: "other" }, capabilities: {} })).toEqual([
    "initialize agreed 2025-03-26; it should agree 2025-11-25",
    "the server names itself other; it should be kalavigyan",
    "the server does not offer tools in its capabilities"
  ]);
});

test("tools/list passes when every public read tool is listed once with an object schema", () => {
  expect(toolListProblems({ tools: LISTED.map(tool) })).toEqual([]);
});

test("tools/list names a missing public tool, a tool listed twice and a tool without a schema", () => {
  const tools = [...LISTED.filter((name) => name !== "get_page").map(tool), tool("find_crafts"), { name: "bare", description: "Bare." }];
  expect(toolListProblems({ tools })).toEqual(["tools/list does not offer get_page", "tools/list offers find_crafts twice", "bare has no object input schema"]);
});

test("a tool error is named with its text and a result without structured content is refused", () => {
  expect(toolContent({ isError: true, content: [{ type: "text", text: "craft_slug is unknown" }] }).problems).toEqual(["the tool answered an error: craft_slug is unknown"]);
  expect(toolContent({ isError: false, content: [] }).problems).toEqual(["the tool result carries no structured content"]);
});

test("find_crafts must find the craft among at most five https-linked crafts", () => {
  expect(foundCraftsProblems(found(["Kutch-Ajrakh", "Bagru-Hand-Block-Print"]), "Kutch-Ajrakh")).toEqual([]);
  expect(foundCraftsProblems(found(["Bagru-Hand-Block-Print"]), "Kutch-Ajrakh")).toEqual(["find_crafts did not find Kutch-Ajrakh"]);
  expect(foundCraftsProblems(found(["a", "b", "c", "d", "e", "Kutch-Ajrakh"]), "Kutch-Ajrakh")).toEqual(["find_crafts answered 6 crafts; it answers at most 5"]);
  expect(foundCraftsProblems({ ...found(["Kutch-Ajrakh"]), schemaVersion: 2 }, "Kutch-Ajrakh")).toEqual(["find_crafts answers schema 2; the contract is schema 1"]);
});

test("get_facts must cite only the sources it lists", () => {
  expect(craftFactsProblems(facts(["s1", "s2"], ["s1", "s2"]), "Kutch-Ajrakh")).toEqual([]);
  expect(craftFactsProblems(facts(["s1", "s9"], ["s1"]), "Kutch-Ajrakh")).toEqual(["facts cite s9, which the answer does not list among its sources"]);
  expect(craftFactsProblems(facts([], ["s1"]), "Kutch-Ajrakh")).toEqual(["get_facts holds no fact for Kutch-Ajrakh"]);
  expect(craftFactsProblems(facts(["s1"], ["s1"]), "Bastar-Dhokra")).toEqual(["get_facts answered for Kutch-Ajrakh; it was asked for Bastar-Dhokra"]);
});

test("get_page must list the sixteen fields in order with standings that agree with its lists", () => {
  expect(coverageProblems(coverage(["PHYSICS"], ["POLICY"]), "Kutch-Ajrakh")).toEqual([]);
  const disagreeing = coverage(["PHYSICS"], ["POLICY"]);
  disagreeing.coverage.thin = [];
  expect(coverageProblems(disagreeing, "Kutch-Ajrakh")).toEqual(["the thin fields are []; the field counts say [PHYSICS]"]);
  const shuffled = coverage([], []);
  shuffled.coverage.fields = [...shuffled.coverage.fields].reverse();
  expect(coverageProblems(shuffled, "Kutch-Ajrakh")[0]).toMatch(/^get_page lists the fields \[POLICY, SOCIETY/);
});

test("the OAuth metadata must name the API as issuer and resource, the web consent page and PKCE S256", () => {
  const resource = { resource: `${API}/api/mcp`, authorization_servers: [API] };
  const server = {
    issuer: API,
    authorization_endpoint: `${WEB}/oauth/authorize`,
    token_endpoint: `${API}/api/oauth/token`,
    registration_endpoint: `${API}/api/oauth/register`,
    code_challenge_methods_supported: ["S256"]
  };
  expect(metadataProblems(resource, server, { api: API, web: WEB })).toEqual([]);
  expect(metadataProblems(resource, { ...server, issuer: WEB, code_challenge_methods_supported: ["plain"] }, { api: API, web: WEB })).toEqual([
    `the issuer is ${WEB}; it should be ${API}`,
    "the authorization server does not offer PKCE S256"
  ]);
});

test("a Bearer challenge's parameters are read from the header", () => {
  const header = `Bearer error="invalid_token", error_description="The token is unknown.", resource_metadata="${API}/.well-known/oauth-protected-resource/api/mcp"`;
  expect(challengeParameters(header)).toEqual({ error: "invalid_token", error_description: "The token is unknown.", resource_metadata: `${API}/.well-known/oauth-protected-resource/api/mcp` });
});

test("a refusal must carry the expected status, error and resource metadata", () => {
  const metadata = `resource_metadata="${API}/.well-known/oauth-protected-resource/api/mcp"`;
  expect(challengeProblems({ status: 401, challenge: `Bearer scope="read contribute", ${metadata}`, body: {} }, { status: 401, origin: API, error: null })).toEqual([]);
  expect(challengeProblems({ status: 403, challenge: `Bearer error="insufficient_scope", ${metadata}`, body: {} }, { status: 403, origin: API, error: "insufficient_scope" })).toEqual([]);
  expect(challengeProblems({ status: 200, challenge: null, body: {} }, { status: 401, origin: API, error: "invalid_token" })).toEqual([
    "the refusal answered HTTP 200; it should answer 401",
    "the refusal carries no Bearer WWW-Authenticate challenge"
  ]);
  expect(challengeProblems({ status: 401, challenge: 'Bearer error="invalid_token"', body: {} }, { status: 401, origin: API, error: "invalid_token" })).toEqual([
    `the challenge points to no resource metadata; it should point to ${API}/.well-known/oauth-protected-resource/api/mcp`
  ]);
});
