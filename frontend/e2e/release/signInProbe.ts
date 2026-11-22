import { sseFields, splitSseBuffer } from "@/lib/answerStream";

export const SIGN_IN_BUDGET_MS = 10_000;
export const PROBE_SIGN_INS = 2;
export const PROBE_CRAFT = "Kutch-Ajrakh";
export const PROBE_QUESTION = "How do the mordant and the resist pastes work together in Kutch Ajrakh printing?";
export const HEAVY_STEPS: ReadonlySet<string> = new Set(["RESEARCHING", "READING", "COMPOSING", "WRITING_BACK"]);

const ANSWER_WAIT_MS = 180_000;
const REQUEST_TIMEOUT_MS = 90_000;
const JSON_HEADERS = { "content-type": "application/json", accept: "application/json" };

export type Account = { email: string; password: string };
export type SignedIn = { token: string | null; ms: number; problem: string | null };
type Clock = () => number;
type LoginBody = { accessToken?: string; two_factor_required?: boolean };

export async function timedSignIn(api: string, account: Account, clock: Clock = Date.now): Promise<SignedIn> {
  const started = clock();
  const response = await fetch(`${api}/api/auth/login`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ email: account.email, password: account.password }),
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS)
  });
  const body = (await response.json().catch(() => ({}))) as LoginBody;
  const ms = clock() - started;
  if (!response.ok) return { token: null, ms, problem: `sign-in answered HTTP ${response.status}` };
  if (body.two_factor_required) return { token: null, ms, problem: "the E2E account asks for two-step verification, so the probe cannot sign in" };
  return body.accessToken ? { token: body.accessToken, ms, problem: null } : { token: null, ms, problem: "sign-in answered without a token" };
}

export function signInProblems(timings: readonly number[], budgetMs: number = SIGN_IN_BUDGET_MS): string[] {
  return timings
    .filter((ms) => ms > budgetMs)
    .map((ms) => `sign-in took ${(ms / 1000).toFixed(1)} s while an Expert answer ran, over its ${budgetMs / 1000} s budget`);
}

export function heavyStep(block: string): string | null {
  const { name, data } = sseFields(block);
  if (data === null) return null;
  if (name === "error" || name === "done") return name;
  if (name !== "status") return null;
  const step = (JSON.parse(data) as { step?: string }).step ?? "";
  return HEAVY_STEPS.has(step) ? step : null;
}

export async function untilHeavy(stream: ReadableStream<Uint8Array>, waitMs: number = ANSWER_WAIT_MS): Promise<string | null> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  const deadline = Date.now() + waitMs;
  let buffer = "";
  while (Date.now() < deadline) {
    const { value, done } = await reader.read();
    if (done) return "the Expert answer ended before its research began";
    const { blocks, rest } = splitSseBuffer(buffer + decoder.decode(value, { stream: true }));
    buffer = rest;
    const reached = blocks.map(heavyStep).find((step) => step !== null);
    if (reached === "error" || reached === "done") return `the Expert answer sent ${reached} before its research began`;
    if (reached) return null;
  }
  return `the Expert answer did not start its research within ${waitMs / 1000} s`;
}

async function expertAnswer(api: string, token: string, signal: AbortSignal): Promise<Response> {
  return fetch(`${api}/api/answers/stream`, {
    method: "POST",
    headers: { ...JSON_HEADERS, accept: "text/event-stream", authorization: `Bearer ${token}` },
    body: JSON.stringify({ question: PROBE_QUESTION, depth: "EXPERT", craftSlug: PROBE_CRAFT, fresh: true }),
    signal
  });
}

async function timingsBeside(api: string, account: Account): Promise<{ timings: number[]; problems: string[] }> {
  const timings: number[] = [];
  for (let at = 0; at < PROBE_SIGN_INS; at += 1) {
    const again = await timedSignIn(api, account);
    if (again.problem) return { timings, problems: [again.problem] };
    timings.push(again.ms);
  }
  return { timings, problems: [] };
}

export async function probeSignInBesideExpert(api: string, account: Account): Promise<string[]> {
  const first = await timedSignIn(api, account);
  if (!first.token) return [first.problem ?? "sign-in answered without a token"];
  const controller = new AbortController();
  try {
    const answer = await expertAnswer(api, first.token, controller.signal);
    if (!answer.ok || !answer.body) return [`the Expert answer answered HTTP ${answer.status}`];
    const waiting = await untilHeavy(answer.body);
    if (waiting) return [waiting];
    const { timings, problems } = await timingsBeside(api, account);
    return [...problems, ...signInProblems(timings)];
  } finally {
    controller.abort();
  }
}
