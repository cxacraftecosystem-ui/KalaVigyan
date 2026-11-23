import { auth } from "@modelcontextprotocol/client";
import { expect, test, type Page } from "@playwright/test";

import { roleCredentials, type Credentials } from "../production/run";

import { approveInBrowser } from "./consent";
import { MCP_PATH } from "./mcpContract";
import {
  CONTRIBUTION_CRAFT,
  CONTRIBUTION_FIELD,
  CONTRIBUTION_SCOPE,
  RETRACTION_REASON,
  closedReading,
  documentHolds,
  fieldClaims,
  listedCitations,
  proposalArguments,
  proposalState,
  queuedProposal,
  quoteFrom,
  readerFactProblems,
  readerProblems,
  readText,
  sourceChoices,
  type SourceChoice
} from "./mcpContribution";
import { ExchangeLog, MemoryOAuthProvider, REDIRECT_URI, callbackOf } from "./mcpOAuth";
import { callTool, getJson } from "./mcpWire";
import { checkRecord, keepRecord } from "./report";
import { apiOrigin, siteOrigin } from "./site";

type Json = Record<string, unknown>;
type Run = { api: string; server: string; token: string };
type Proposal = { claimId: string; source: SourceChoice; reply: Json | null };

const CHECK = "mcp-contribution";
const RUN_TIMEOUT_MS = 15 * 60_000;
const POLL_MS = 5_000;
const PROPOSAL_WAIT_MS = 4 * 60_000;
const PAGE_WAIT_MS = 6 * 60_000;
const FINISHED = new Set(["DONE", "FAILED"]);
const PROFESSOR_SECRETS = "Set E2E_PROFESSOR_EMAIL, E2E_PROFESSOR_PASSWORD and E2E_PROFESSOR_TOTP_SECRET: only a Professor's fact is published at once";
const FACT_QUERY = "release check withdrawn";

function settled(name: string, problems: string[]): void {
  keepRecord(checkRecord(CHECK, name, problems));
  expect(problems, `${name}: ${problems.join("; ")}`).toEqual([]);
}

async function pause(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function polled<T>(probe: () => Promise<T | null>, waitMs: number): Promise<T | null> {
  const deadline = Date.now() + waitMs;
  for (;;) {
    const found = await probe();
    if (found !== null || Date.now() > deadline) return found;
    await pause(POLL_MS);
  }
}

async function tool(run: Run, name: string, args: Json, signedIn: boolean): Promise<Json> {
  const { content, problems } = await callTool(run.server, name, args, signedIn ? run.token : undefined);
  if (!content) throw new Error(`${name}: ${problems.join("; ")}`);
  return content;
}

async function signedInRun(page: Page, account: Credentials): Promise<Run> {
  const api = apiOrigin();
  const server = new URL(MCP_PATH, api);
  const provider = new MemoryOAuthProvider(CONTRIBUTION_SCOPE);
  const log = new ExchangeLog();
  const first = await auth(provider, { serverUrl: server, scope: CONTRIBUTION_SCOPE, fetchFn: log.fetch });
  if (first !== "REDIRECT" || !provider.authorizationUrl) throw new Error(`auth answered ${first}; a first sign-in redirects`);
  const { redirectTo } = await approveInBrowser(page, provider.authorizationUrl, account, REDIRECT_URI);
  const back = callbackOf(redirectTo);
  const second = await auth(provider, { serverUrl: server, authorizationCode: back.code, iss: back.iss ?? undefined, fetchFn: log.fetch });
  const token = provider.tokens()?.access_token;
  if (second !== "AUTHORIZED" || !token) throw new Error(`the token exchange answered ${second}`);
  return { api, server: server.href, token };
}

async function closedSource(run: Run): Promise<{ source: SourceChoice; quote: string }> {
  const facts = await tool(run, "get_facts", { craft_slug: CONTRIBUTION_CRAFT, limit: 50 }, true);
  for (const source of sourceChoices(facts)) {
    const answer = await tool(run, "read_source", { url: source.url }, true).catch(() => null);
    const reading = answer ? readText(answer) : null;
    const quote = reading && closedReading(reading) ? quoteFrom(reading) : null;
    if (quote) return { source, quote };
  }
  throw new Error(`no source of ${CONTRIBUTION_CRAFT} without an open licence could be read for a quote`);
}

async function coverageClaims(run: Run): Promise<number | null> {
  const answer = await getJson(`${run.api}/api/crafts/${CONTRIBUTION_CRAFT}/coverage`);
  return answer.status === 200 && typeof answer.body === "object" && answer.body ? fieldClaims(answer.body as Json, CONTRIBUTION_FIELD) : null;
}

async function finishedReply(run: Run, proposalId: string): Promise<Json | null> {
  const done = await polled(async () => {
    const found = proposalState(await tool(run, "get_proposal", { proposal_id: proposalId }, true));
    return FINISHED.has(found.state) ? found : null;
  }, PROPOSAL_WAIT_MS);
  return done?.reply ?? null;
}

async function proposed(run: Run): Promise<Proposal> {
  const { source, quote } = await closedSource(run);
  const batch = await tool(run, "propose_facts", proposalArguments(source, quote, `${Date.now()}`), true);
  const queued = queuedProposal(batch);
  settled("propose_facts queues a fact quoting a page with no open licence", queued.problems);
  const reply = await finishedReply(run, queued.id ?? "");
  return { claimId: typeof reply?.claimId === "string" ? reply.claimId : "", source, reply };
}

async function readerFacts(run: Run): Promise<Json> {
  return tool(run, "get_facts", { craft_slug: CONTRIBUTION_CRAFT, field: CONTRIBUTION_FIELD, query: FACT_QUERY, limit: 20 }, false);
}

async function pageHolds(run: Run, claimId: string): Promise<boolean> {
  const answer = await getJson(`${run.api}/api/crafts/${CONTRIBUTION_CRAFT}/monograph`);
  return answer.status === 200 && typeof answer.body === "object" && answer.body !== null && documentHolds(answer.body as Json, claimId);
}

async function readersSee(run: Run, made: Proposal, before: number | null): Promise<void> {
  settled("get_facts shows the fact to a signed-out reader with its citation and no quote", readerFactProblems(await readerFacts(run), made.claimId, made.source));
  const counted = await coverageClaims(run);
  settled("the coverage count of the field grows by the fact", before !== null && counted === before + 1 ? [] : [`the ${CONTRIBUTION_FIELD} count went from ${before} to ${counted}`]);
  const shown = await polled(async () => ((await pageHolds(run, made.claimId)) ? true : null), PAGE_WAIT_MS);
  settled("the craft page lists the fact for a signed-out reader", shown ? [] : [`the ${CONTRIBUTION_CRAFT} page did not list fact ${made.claimId} within ${PAGE_WAIT_MS / 60_000} minutes`]);
}

async function retract(page: Page, claimId: string): Promise<number> {
  await page.goto(siteOrigin(), { waitUntil: "domcontentloaded" });
  return page.evaluate(
    async ({ path, reason }) => (await fetch(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ reason }) })).status,
    { path: `/api/review-queue/FACTS/${claimId}/retract`, reason: RETRACTION_REASON }
  );
}

async function goneFromReaders(run: Run, claimId: string, before: number | null): Promise<void> {
  const facts = await readerFacts(run);
  const counted = await coverageClaims(run);
  const problems = listedCitations(facts, claimId) ? [`get_facts still shows the retracted fact ${claimId}`] : [];
  if (counted !== before) problems.push(`the ${CONTRIBUTION_FIELD} count is ${counted} after the retraction, not ${before}`);
  settled("the retracted fact is gone from readers and from the count", problems);
}

test("a Professor's fact proposed through MCP from a closed page is seen by a signed-out reader, then retracted", async ({ page }) => {
  test.setTimeout(RUN_TIMEOUT_MS);
  const account = roleCredentials("PROFESSOR");
  if (!account) throw new Error(PROFESSOR_SECRETS);
  const run = await test.step("the Professor signs an MCP client in with the contribute scope", () => signedInRun(page, account));
  const before = await coverageClaims(run);
  const made = await test.step("propose_facts queues a test fact quoting a closed page", () => proposed(run));
  try {
    settled("the reply says the fact is published and where a signed-out reader sees it", readerProblems(made.reply));
    await test.step("get_facts, the coverage count and the craft page show it to a signed-out reader", () => readersSee(run, made, before));
  } finally {
    const status = made.claimId ? await retract(page, made.claimId) : 0;
    settled("the Professor retracts the test fact", status === 200 || made.reply?.outcome === "REFUSED" ? [] : [`the retraction answered ${status}`]);
  }
  await test.step("the retracted fact is gone for readers", () => goneFromReaders(run, made.claimId, before));
});
