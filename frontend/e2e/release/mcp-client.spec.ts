import { Client, StreamableHTTPClientTransport, auth } from "@modelcontextprotocol/client";
import { expect, test, type Page } from "@playwright/test";

import { credentials } from "../production/run";

import { approveInBrowser } from "./consent";
import { challengeProblems } from "./mcpChallenge";
import { authorizationProblems, revocationBody, tokenProblems } from "./mcpClientRules";
import { CHECKED_CRAFT, CHECKED_QUERY, MCP_PATH, SCOPED_TOOL, foundCraftsProblems, toolListProblems } from "./mcpContract";
import { CLIENT_SCOPE, ExchangeLog, MemoryOAuthProvider, REDIRECT_URI, callbackOf, type Callback } from "./mcpOAuth";
import { rpc } from "./mcpWire";
import { checkRecord, keepRecord } from "./report";
import { apiOrigin, siteOrigin } from "./site";

const CHECK = "mcp-client";
const CLIENT_INFO = { name: "kalavigyan-release-gate", version: "1.0.0" };
const RUN_TIMEOUT_MS = 6 * 60_000;
const FORGED_TOKEN = "kvmcp_at_forged-by-the-release-gate";

type Run = { api: string; server: URL; provider: MemoryOAuthProvider; log: ExchangeLog; revoked: boolean };

function settled(name: string, problems: string[]): void {
  keepRecord(checkRecord(CHECK, name, problems));
  expect(problems, `${name}: ${problems.join("; ")}`).toEqual([]);
}

async function revoke(run: Run): Promise<number> {
  const body = revocationBody(run.provider.tokens()?.refresh_token ?? "", run.provider.clientInformation()?.client_id ?? "");
  const response = await fetch(`${run.api}/api/oauth/revoke`, { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" }, body });
  run.revoked = response.status === 200;
  return response.status;
}

async function register(run: Run): Promise<void> {
  const outcome = await auth(run.provider, { serverUrl: run.server, scope: CLIENT_SCOPE, fetchFn: run.log.fetch });
  const expected = { web: siteOrigin(), resource: run.server.href, clientId: run.provider.clientInformation()?.client_id ?? null };
  settled("registration and authorization request", outcome === "REDIRECT" ? authorizationProblems(run.provider.authorizationUrl, expected) : [`auth answered ${outcome}; a first sign-in redirects`]);
}

async function consent(run: Run, page: Page): Promise<Callback> {
  const asked = run.provider.authorizationUrl;
  if (!asked) throw new Error("the client was never sent to sign in");
  const { redirectTo, acceptedTerms } = await approveInBrowser(page, asked, credentials(), REDIRECT_URI);
  const returned = callbackOf(redirectTo);
  settled(acceptedTerms ? "consent, accepting the terms of use" : "consent", returned.state === run.provider.expectedState ? [] : ["the consent returned another state than the client sent"]);
  return returned;
}

async function exchange(run: Run, callback: Callback): Promise<void> {
  const outcome = await auth(run.provider, { serverUrl: run.server, authorizationCode: callback.code, iss: callback.iss ?? undefined, fetchFn: run.log.fetch });
  settled("token exchange", outcome === "AUTHORIZED" ? tokenProblems(run.provider.tokens()) : [`auth answered ${outcome} with a code; it should authorize`]);
}

async function useTools(run: Run): Promise<void> {
  const client = new Client(CLIENT_INFO);
  try {
    await client.connect(new StreamableHTTPClientTransport(run.server, { authProvider: run.provider, fetch: run.log.fetch }));
    settled("tools/list with the bearer", toolListProblems({ tools: (await client.listTools()).tools }));
    const result = await client.callTool({ name: "find_crafts", arguments: { query: CHECKED_QUERY } });
    const found = result.isError ? ["find_crafts answered an error"] : foundCraftsProblems((result.structuredContent ?? {}) as Record<string, unknown>, CHECKED_CRAFT);
    const strays = run.log.to(MCP_PATH).filter((sent) => sent.method === "POST" && (!sent.bearer || sent.status >= 400));
    settled(`find_crafts ${CHECKED_QUERY} with the bearer`, [...found, ...strays.map((sent) => `an MCP POST went ${sent.bearer ? "with" : "without"} the bearer and answered ${sent.status}`)]);
  } finally {
    await client.close();
  }
}

async function refusals(run: Run): Promise<void> {
  const access = run.provider.tokens()?.access_token ?? "";
  const scoped = await rpc(run.server.href, "tools/call", { name: SCOPED_TOOL, arguments: {} }, access);
  settled(`${SCOPED_TOOL} with a read token`, challengeProblems(scoped, { status: 403, origin: run.api, error: "insufficient_scope" }));
  const forged = await rpc(run.server.href, "tools/list", {}, FORGED_TOKEN);
  settled("a forged bearer", challengeProblems(forged, { status: 401, origin: run.api, error: "invalid_token" }));
}

async function revocation(run: Run): Promise<void> {
  const access = run.provider.tokens()?.access_token ?? "";
  const status = await revoke(run);
  const after = await rpc(run.server.href, "tools/list", {}, access);
  const problems = status === 200 ? [] : [`revocation answered ${status}`];
  settled("revocation ends the connection", [...problems, ...challengeProblems(after, { status: 401, origin: run.api, error: "invalid_token" })]);
}

test("a real MCP client registers, signs in with PKCE through the consent page, lists the tools and calls one", async ({ page }) => {
  test.setTimeout(RUN_TIMEOUT_MS);
  const api = apiOrigin();
  const run: Run = { api, server: new URL(MCP_PATH, api), provider: new MemoryOAuthProvider(), log: new ExchangeLog(), revoked: false };
  try {
    await test.step("discovery and dynamic client registration start a PKCE sign-in", () => register(run));
    const callback = await test.step("the E2E account approves on the consent page", () => consent(run, page));
    await test.step("the code and its verifier are exchanged for tokens", () => exchange(run, callback));
    await test.step("tools/list and find_crafts over Streamable HTTP with the bearer", () => useTools(run));
    await test.step("a tool beyond the scope and a forged bearer are refused with challenges", () => refusals(run));
    await test.step("revoking the connection ends its access token", () => revocation(run));
  } finally {
    if (!run.revoked && run.provider.tokens()?.refresh_token) await revoke(run);
  }
});
