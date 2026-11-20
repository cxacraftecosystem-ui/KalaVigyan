import { PKCE_METHOD } from "./mcpContract";
import { CLIENT_SCOPE, REDIRECT_URI } from "./mcpOAuth";

export type AuthorizationExpectation = { web: string; resource: string; clientId: string | null };

export type HeldTokens = { access_token?: string; token_type?: string; refresh_token?: string; scope?: string; expires_in?: number };

export const ACCESS_PREFIX = "kvmcp_at_";
export const REFRESH_PREFIX = "kvmcp_rt_";
export const ACCESS_SECONDS = 3600;

const CHALLENGE = /^[A-Za-z0-9_-]{43}$/;
const AUTHORIZE_PATH = "/oauth/authorize";

function parameterProblems(params: URLSearchParams, expected: AuthorizationExpectation): string[] {
  const wanted: Record<string, string | null> = {
    response_type: "code",
    code_challenge_method: PKCE_METHOD,
    client_id: expected.clientId,
    redirect_uri: REDIRECT_URI,
    resource: expected.resource,
    scope: CLIENT_SCOPE
  };
  const problems = Object.entries(wanted)
    .filter(([name, value]) => value === null || params.get(name) !== value)
    .map(([name, value]) => `the authorization request sends ${name}=${params.get(name) ?? "nothing"}; it should send ${value ?? "the registered client id"}`);
  if (!CHALLENGE.test(params.get("code_challenge") ?? "")) problems.push("the authorization request sends no S256 code challenge of 43 characters");
  if (!params.get("state")) problems.push("the authorization request sends no state");
  return problems;
}

export function authorizationProblems(url: URL | null, expected: AuthorizationExpectation): string[] {
  if (!url) return ["the client was never sent to sign in"];
  const page = `${url.origin}${url.pathname}`;
  const problems = page === `${expected.web}${AUTHORIZE_PATH}` ? [] : [`the client was sent to ${page}; the consent page is ${expected.web}${AUTHORIZE_PATH}`];
  return [...problems, ...parameterProblems(url.searchParams, expected)];
}

export function tokenProblems(tokens: HeldTokens | undefined): string[] {
  if (!tokens) return ["the client holds no tokens after the exchange"];
  const problems: string[] = [];
  if ((tokens.token_type ?? "").toLowerCase() !== "bearer") problems.push(`the token type is ${tokens.token_type ?? "absent"}; it should be Bearer`);
  if (!(tokens.access_token ?? "").startsWith(ACCESS_PREFIX)) problems.push("the access token is not a KalaVigyan access token");
  if (!(tokens.refresh_token ?? "").startsWith(REFRESH_PREFIX)) problems.push("the reply carries no KalaVigyan refresh token");
  if (tokens.scope !== CLIENT_SCOPE) problems.push(`the token holds the scopes ${tokens.scope ?? "none"}; it was asked for ${CLIENT_SCOPE}`);
  if (tokens.expires_in !== ACCESS_SECONDS) problems.push(`the access token lives ${tokens.expires_in ?? "an unknown number of"} seconds; it should live ${ACCESS_SECONDS}`);
  return problems;
}

export function revocationBody(token: string, clientId: string): string {
  return new URLSearchParams({ token, client_id: clientId }).toString();
}
