import { MCP_PATH } from "./mcpContract";
import type { Answer } from "./mcpWire";

export type ChallengeExpectation = { status: 401 | 403; origin: string; error: string | null };

const BEARER = "Bearer ";
const PARAMETER = /([a-z_]+)="([^"]*)"/g;

export function challengeParameters(challenge: string): Record<string, string> {
  const found: Record<string, string> = {};
  for (const [, name, value] of challenge.matchAll(PARAMETER)) found[name] = value;
  return found;
}

export function resourceMetadataUrl(origin: string): string {
  return `${origin}/.well-known/oauth-protected-resource${MCP_PATH}`;
}

export function challengeProblems(answer: Answer, expected: ChallengeExpectation): string[] {
  const problems: string[] = [];
  if (answer.status !== expected.status) problems.push(`the refusal answered HTTP ${answer.status}; it should answer ${expected.status}`);
  if (!answer.challenge?.startsWith(BEARER)) return [...problems, "the refusal carries no Bearer WWW-Authenticate challenge"];
  const parameters = challengeParameters(answer.challenge);
  const metadata = resourceMetadataUrl(expected.origin);
  if (parameters.resource_metadata !== metadata) problems.push(`the challenge points to ${parameters.resource_metadata ?? "no resource metadata"}; it should point to ${metadata}`);
  if (expected.error !== null && parameters.error !== expected.error) problems.push(`the challenge names the error ${parameters.error ?? "none"}; it should name ${expected.error}`);
  if (expected.error === null && parameters.error !== undefined) problems.push(`the challenge names the error ${parameters.error}; a first sign-in names none`);
  return problems;
}
