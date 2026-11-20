import { clip } from "../production/checks";
import { BYPASS_HEADER } from "../production/preview";

import { PROTOCOL_VERSION, replyResult, toolContent } from "./mcpContract";

type Json = Record<string, unknown>;

export type Answer = { status: number; challenge: string | null; body: unknown };

const ANSWER_TIMEOUT_MS = 60_000;

function parsed(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch (error) {
    if (error instanceof SyntaxError) return text;
    throw error;
  }
}

async function answerOf(response: Response): Promise<Answer> {
  return { status: response.status, challenge: response.headers.get("www-authenticate"), body: parsed(await response.text()) };
}

export async function getJson(url: string): Promise<Answer> {
  return answerOf(await fetch(url, { headers: { accept: "application/json" }, signal: AbortSignal.timeout(ANSWER_TIMEOUT_MS) }));
}

export async function rpc(endpoint: string, method: string, params: Json, token?: string, bypass?: string): Promise<Answer> {
  const headers: Record<string, string> = { "content-type": "application/json", accept: "application/json", "mcp-protocol-version": PROTOCOL_VERSION };
  if (token) headers.authorization = `Bearer ${token}`;
  if (bypass) headers[BYPASS_HEADER] = bypass;
  const body = JSON.stringify({ jsonrpc: "2.0", id: 1, method, params });
  return answerOf(await fetch(endpoint, { method: "POST", headers, body, signal: AbortSignal.timeout(ANSWER_TIMEOUT_MS) }));
}

export function answerResult(answer: Answer): { result: Json | null; problems: string[] } {
  if (answer.status !== 200) {
    const text = typeof answer.body === "string" ? answer.body : JSON.stringify(answer.body);
    return { result: null, problems: [`the server answered HTTP ${answer.status}: ${clip(text)}`] };
  }
  return replyResult(answer.body);
}

export async function callTool(endpoint: string, name: string, args: Json, token?: string): Promise<{ content: Json | null; problems: string[] }> {
  const { result, problems } = answerResult(await rpc(endpoint, "tools/call", { name, arguments: args }, token));
  if (!result) return { content: null, problems };
  const called = toolContent(result);
  return { content: called.content, problems: [...problems, ...called.problems] };
}
