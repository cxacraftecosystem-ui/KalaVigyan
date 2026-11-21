import { listText } from "@/lib/format";
import {
  AUTHORIZATION_PARAMS,
  MCP_SCOPES,
  type AuthorizationPrompt,
  type AuthorizationQuery,
  type McpScope,
  type ScopeChoice
} from "@/lib/oauthContract";

export const ALWAYS_GIVEN: McpScope = "read";
export const TERMS_NEEDED = "Accept the terms of use to connect the app.";
export const MISSING_REQUEST = "This link is missing what the app sends. Start the connection again from the app.";

const NAVIGABLE = /^(https?:|[a-z][a-z0-9+.-]*:)/i;
const NEVER_NAVIGATE = /^(javascript|data|vbscript|file|blob|about):/i;
const LOOPBACK_HOST = /^(localhost|::1|\[::1\]|127(\.\d{1,3}){3})$/i;

export type IdentityFact = { label: string; value: string };

export function authorizationQuery(search: string): AuthorizationQuery | null {
  const params = new URLSearchParams(search);
  const query: Partial<Record<string, string>> = {};
  for (const name of AUTHORIZATION_PARAMS) {
    const value = params.get(name);
    if (value !== null && value !== "") query[name] = value;
  }
  if (!query.client_id || !query.redirect_uri) return null;
  return query as AuthorizationQuery;
}

export function initialScopes(prompt: AuthorizationPrompt): McpScope[] {
  return inOrder(prompt.scopes.filter((choice) => choice.allowed).map((choice) => choice.scope));
}

export function choosableScope(choice: ScopeChoice): boolean {
  return choice.allowed && choice.scope !== ALWAYS_GIVEN;
}

export function withScope(chosen: readonly McpScope[], scope: McpScope, on: boolean): McpScope[] {
  if (scope === ALWAYS_GIVEN) return inOrder(chosen);
  return inOrder(on ? [...chosen, scope] : chosen.filter((item) => item !== scope));
}

export function needsTerms(prompt: AuthorizationPrompt): boolean {
  return prompt.terms.acceptedAt === null;
}

export function consentProblem(prompt: AuthorizationPrompt, termsTicked: boolean): string | null {
  return needsTerms(prompt) && !termsTicked ? TERMS_NEEDED : null;
}

export function consentBody(query: AuthorizationQuery, prompt: AuthorizationPrompt, chosen: readonly McpScope[]): Record<string, unknown> {
  const allowed = new Set(prompt.scopes.filter((choice) => choice.allowed).map((choice) => choice.scope));
  return {
    request: query,
    scopes: inOrder([ALWAYS_GIVEN, ...chosen.filter((scope) => allowed.has(scope))]),
    termsVersion: prompt.terms.version
  };
}

export function navigableRedirect(url: string): boolean {
  const trimmed = url.trim();
  return NAVIGABLE.test(trimmed) && !NEVER_NAVIGATE.test(trimmed);
}

export function scopeList(scopes: readonly McpScope[]): string {
  return listText(inOrder(scopes));
}

export function returnsToThisDevice(prompt: AuthorizationPrompt): boolean {
  return LOOPBACK_HOST.test(prompt.redirectHost);
}

export function identityFacts(prompt: AuthorizationPrompt): IdentityFact[] {
  const asked = scopeList(prompt.scopes.map((choice) => choice.scope));
  return [
    { label: "App", value: prompt.clientName },
    { label: "Identity", value: prompt.clientIdHost ? `Published at ${prompt.clientIdHost}` : "Registered by the app itself" },
    { label: "Returns you to", value: prompt.redirectHost },
    { label: "Asks to", value: `${asked.charAt(0).toUpperCase()}${asked.slice(1)}` }
  ];
}

export function deviceCaution(prompt: AuthorizationPrompt): string {
  return `This sign-in returns to a program on this computer. Approve it only if you started it from ${prompt.clientName} here.`;
}

function inOrder(scopes: readonly McpScope[]): McpScope[] {
  const present = new Set(scopes);
  return MCP_SCOPES.filter((scope) => present.has(scope));
}
