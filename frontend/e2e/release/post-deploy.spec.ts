import { expect, test } from "@playwright/test";

import { passPreviewProtection } from "../production/preview";

import { KEY_PAGES, pageProblems } from "./keyPages";
import {
  CHECKED_CRAFT,
  CHECKED_QUERY,
  MCP_PATH,
  PROTOCOL_VERSION,
  SCOPED_TOOL,
  coverageProblems,
  craftFactsProblems,
  foundCraftsProblems,
  initializeProblems,
  metadataProblems,
  toolListProblems
} from "./mcpContract";
import { challengeProblems } from "./mcpChallenge";
import { answerResult, callTool, getJson, rpc, type Answer } from "./mcpWire";
import { visitKeyPage } from "./pageVisit";
import { checkRecord, keepRecord } from "./report";
import { apiOrigin, bypassToken, siteOrigin } from "./site";

const PAGE_CHECK = "page";
const MCP_CHECK = "mcp";
const CLIENT_INFO = { name: "kalavigyan-post-deploy", version: "1.0.0" };

type Json = Record<string, unknown>;

function settle(check: string, target: string, problems: string[]): void {
  keepRecord(checkRecord(check, target, problems));
  expect(problems, `${target}: ${problems.join("; ")}`).toEqual([]);
}

function listed(answer: Answer): string[] {
  const { result, problems } = answerResult(answer);
  return result ? [...problems, ...toolListProblems(result)] : problems;
}

function bodyOf(answer: Answer, what: string): { body: Json | null; problems: string[] } {
  const body = typeof answer.body === "object" && answer.body !== null && !Array.isArray(answer.body) ? (answer.body as Json) : null;
  if (answer.status === 200 && body) return { body, problems: [] };
  return { body: null, problems: [`${what} answered HTTP ${answer.status}`] };
}

function mcpEndpoint(): string {
  return `${apiOrigin()}${MCP_PATH}`;
}

test.describe("key pages", () => {
  test.beforeEach(async ({ context }) => {
    await passPreviewProtection(context, siteOrigin(), bypassToken());
  });

  for (const keyPage of KEY_PAGES) {
    test(`${keyPage.name} answers and draws its marker`, async ({ page }) => {
      const seen = await visitKeyPage(page, keyPage);
      settle(PAGE_CHECK, `${keyPage.name} (${keyPage.path})`, pageProblems(keyPage, seen));
    });
  }
});

test.describe("public MCP tools", () => {
  test("initialize names the server and its protocol", async () => {
    const { result, problems } = answerResult(await rpc(mcpEndpoint(), "initialize", { protocolVersion: PROTOCOL_VERSION, capabilities: {}, clientInfo: CLIENT_INFO }));
    settle(MCP_CHECK, "initialize", result ? [...problems, ...initializeProblems(result)] : problems);
  });

  test("tools/list through the API lists the public tools", async () => {
    settle(MCP_CHECK, "tools/list through the API", listed(await rpc(mcpEndpoint(), "tools/list", {})));
  });

  test("tools/list through the site lists the public tools", async () => {
    settle(MCP_CHECK, "tools/list through the site", listed(await rpc(`${siteOrigin()}${MCP_PATH}`, "tools/list", {})));
  });

  test(`find_crafts finds ${CHECKED_CRAFT}`, async () => {
    const { content, problems } = await callTool(mcpEndpoint(), "find_crafts", { query: CHECKED_QUERY });
    settle(MCP_CHECK, `find_crafts ${CHECKED_QUERY}`, content ? [...problems, ...foundCraftsProblems(content, CHECKED_CRAFT)] : problems);
  });

  test(`get_facts gives ${CHECKED_CRAFT}'s cited facts`, async () => {
    const { content, problems } = await callTool(mcpEndpoint(), "get_facts", { craft_slug: CHECKED_CRAFT });
    settle(MCP_CHECK, `get_facts ${CHECKED_CRAFT}`, content ? [...problems, ...craftFactsProblems(content, CHECKED_CRAFT)] : problems);
  });

  test(`get_coverage gives ${CHECKED_CRAFT}'s sixteen fields`, async () => {
    const { content, problems } = await callTool(mcpEndpoint(), "get_coverage", { craft_slug: CHECKED_CRAFT });
    settle(MCP_CHECK, `get_coverage ${CHECKED_CRAFT}`, content ? [...problems, ...coverageProblems(content, CHECKED_CRAFT)] : problems);
  });

  test("a signed-in tool asks an anonymous caller to sign in", async () => {
    const answer = await rpc(mcpEndpoint(), "tools/call", { name: SCOPED_TOOL, arguments: {} });
    settle(MCP_CHECK, `${SCOPED_TOOL} without a token`, challengeProblems(answer, { status: 401, origin: apiOrigin(), error: null }));
  });

  test("the sign-in metadata names the issuer and its endpoints", async () => {
    const api = apiOrigin();
    const resource = bodyOf(await getJson(`${api}/.well-known/oauth-protected-resource${MCP_PATH}`), "the protected resource metadata");
    const server = bodyOf(await getJson(`${api}/.well-known/oauth-authorization-server`), "the authorization server metadata");
    const problems = [...resource.problems, ...server.problems];
    if (resource.body && server.body) problems.push(...metadataProblems(resource.body, server.body, { api, web: siteOrigin() }));
    settle(MCP_CHECK, "OAuth metadata", problems);
  });
});
