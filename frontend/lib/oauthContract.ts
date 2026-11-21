import { apiFetch, buildQuery } from "@/lib/api";
import { boolean, list, nullable, object, oneOf, optional, parseShape, tagged, text, type Shape } from "@/lib/shape";

export const OAUTH_TERMS_PATH = "/oauth/terms";
export const OAUTH_REVIEW_PATH = "/oauth/authorize/request";
export const OAUTH_APPROVE_PATH = "/oauth/authorize/approve";
export const OAUTH_DENY_PATH = "/oauth/authorize/deny";
export const OAUTH_CONNECTIONS_PATH = "/oauth/connections";
export const OAUTH_CONNECTION_PATH = (id: string) => `/oauth/connections/${encodeURIComponent(id)}`;

export const MCP_SCOPES = ["read", "ask", "contribute", "review"] as const;
export const AUTHORIZATION_PARAMS = [
  "client_id",
  "redirect_uri",
  "response_type",
  "code_challenge",
  "code_challenge_method",
  "state",
  "scope",
  "resource"
] as const;

export type McpScope = (typeof MCP_SCOPES)[number];
export type AuthorizationParam = (typeof AUTHORIZATION_PARAMS)[number];
export type AuthorizationQuery = Partial<Record<AuthorizationParam, string>> & { client_id: string; redirect_uri: string };

export type ScopeChoice = { scope: McpScope; title: string; description: string; allowed: boolean; needs: string | null };
export type TermsStatus = { version: string; acceptedAt: string | null };
export type AuthorizationPrompt = {
  kind: "prompt";
  clientName: string;
  clientIdHost?: string | null;
  redirectHost: string;
  scopes: ScopeChoice[];
  terms: TermsStatus;
};
export type AuthorizationRedirect = { kind: "redirect"; redirectTo: string };
export type AuthorizationReview = AuthorizationPrompt | AuthorizationRedirect;
export type TermsOfUse = { version: string; title: string; body: string };
export type Connection = {
  id: string;
  clientName: string;
  clientHost: string;
  scopes: McpScope[];
  connectedAt: string;
  lastUsedAt: string | null;
};
export type ConnectionList = { serverUrl: string | null; connections: Connection[] };

const scopeChoiceShape: Shape<ScopeChoice> = object<ScopeChoice>({
  scope: oneOf(MCP_SCOPES),
  title: text,
  description: text,
  allowed: boolean,
  needs: nullable(text)
});

export const promptShape: Shape<AuthorizationPrompt> = object<AuthorizationPrompt>({
  kind: oneOf(["prompt"] as const),
  clientName: text,
  clientIdHost: optional(nullable(text)),
  redirectHost: text,
  scopes: list(scopeChoiceShape),
  terms: object<TermsStatus>({ version: text, acceptedAt: nullable(text) })
});

export const redirectShape: Shape<AuthorizationRedirect> = object<AuthorizationRedirect>({ kind: oneOf(["redirect"] as const), redirectTo: text });

export const reviewShape: Shape<AuthorizationReview> = tagged<AuthorizationReview>("kind", { prompt: promptShape, redirect: redirectShape });

export const termsShape: Shape<TermsOfUse> = object<TermsOfUse>({ version: text, title: text, body: text });

export const connectionListShape: Shape<ConnectionList> = object<ConnectionList>({
  serverUrl: nullable(text),
  connections: list(
    object<Connection>({
      id: text,
      clientName: text,
      clientHost: text,
      scopes: list(oneOf(MCP_SCOPES)),
      connectedAt: text,
      lastUsedAt: nullable(text)
    })
  )
});

export async function fetchAuthorizationReview(query: AuthorizationQuery): Promise<AuthorizationReview> {
  return parseShape(reviewShape, await apiFetch<unknown>(`${OAUTH_REVIEW_PATH}${buildQuery(query)}`));
}

export async function fetchTermsOfUse(): Promise<TermsOfUse> {
  return parseShape(termsShape, await apiFetch<unknown>(OAUTH_TERMS_PATH));
}

export async function approveAuthorization(body: Record<string, unknown>): Promise<AuthorizationRedirect> {
  return parseShape(redirectShape, await apiFetch<unknown>(OAUTH_APPROVE_PATH, { method: "POST", body: JSON.stringify(body) }));
}

export async function denyAuthorization(query: AuthorizationQuery): Promise<AuthorizationRedirect> {
  return parseShape(redirectShape, await apiFetch<unknown>(OAUTH_DENY_PATH, { method: "POST", body: JSON.stringify({ request: query }) }));
}

export async function fetchConnections(): Promise<ConnectionList> {
  return parseShape(connectionListShape, await apiFetch<unknown>(OAUTH_CONNECTIONS_PATH));
}

export async function revokeConnection(id: string): Promise<void> {
  await apiFetch<void>(OAUTH_CONNECTION_PATH(id), { method: "DELETE" });
}
