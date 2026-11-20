import { expect, test } from "@playwright/test";

import { authorizationProblems, revocationBody, tokenProblems } from "./mcpClientRules";
import { MemoryOAuthProvider, REDIRECT_URI, callbackOf } from "./mcpOAuth";

const WEB = "https://web.example";
const RESOURCE = "https://api.example/api/mcp";
const CLIENT_ID = "0b7f6f0e-3c1a-4c55-9a43-0f2b6a1e9d11";
const CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM";

function authorizationUrl(overrides: Record<string, string | null> = {}): URL {
  const url = new URL(`${WEB}/oauth/authorize`);
  const params: Record<string, string | null> = {
    response_type: "code",
    client_id: CLIENT_ID,
    code_challenge: CHALLENGE,
    code_challenge_method: "S256",
    redirect_uri: REDIRECT_URI,
    state: "a-state",
    scope: "read",
    resource: RESOURCE,
    ...overrides
  };
  for (const [name, value] of Object.entries(params)) if (value !== null) url.searchParams.set(name, value);
  return url;
}

const EXPECTED = { web: WEB, resource: RESOURCE, clientId: CLIENT_ID };

test("the client's authorization request carries PKCE S256, the registered client, the resource, read and a state", () => {
  expect(authorizationProblems(authorizationUrl(), EXPECTED)).toEqual([]);
});

test("an authorization request without PKCE, state or the resource is named on each", () => {
  const problems = authorizationProblems(authorizationUrl({ code_challenge_method: "plain", code_challenge: "short", state: null, resource: null }), EXPECTED);
  expect(problems).toEqual([
    "the authorization request sends code_challenge_method=plain; it should send S256",
    `the authorization request sends resource=nothing; it should send ${RESOURCE}`,
    "the authorization request sends no S256 code challenge of 43 characters",
    "the authorization request sends no state"
  ]);
});

test("a client sent to another page than the consent page, or never registered, fails", () => {
  const elsewhere = new URL(authorizationUrl().href.replace(`${WEB}/oauth/authorize`, "https://evil.example/authorize"));
  expect(authorizationProblems(elsewhere, EXPECTED)[0]).toBe(`the client was sent to https://evil.example/authorize; the consent page is ${WEB}/oauth/authorize`);
  expect(authorizationProblems(authorizationUrl(), { ...EXPECTED, clientId: null })).toEqual([`the authorization request sends client_id=${CLIENT_ID}; it should send the registered client id`]);
  expect(authorizationProblems(null, EXPECTED)).toEqual(["the client was never sent to sign in"]);
});

test("the tokens must be a KalaVigyan bearer and refresh token for read, living an hour", () => {
  const good = { access_token: "kvmcp_at_abc", token_type: "Bearer", refresh_token: "kvmcp_rt_def", scope: "read", expires_in: 3600 };
  expect(tokenProblems(good)).toEqual([]);
  expect(tokenProblems({ ...good, token_type: "bearer" })).toEqual([]);
  expect(tokenProblems({ access_token: "other", token_type: "mac", scope: "read ask", expires_in: 60 })).toEqual([
    "the token type is mac; it should be Bearer",
    "the access token is not a KalaVigyan access token",
    "the reply carries no KalaVigyan refresh token",
    "the token holds the scopes read ask; it was asked for read",
    "the access token lives 60 seconds; it should live 3600"
  ]);
  expect(tokenProblems(undefined)).toEqual(["the client holds no tokens after the exchange"]);
});

test("the consent's return carries the code, state and issuer to the registered loopback address", () => {
  expect(callbackOf(`${REDIRECT_URI}?code=kvmcp_ac_x&state=s1&iss=https%3A%2F%2Fapi.example`)).toEqual({ code: "kvmcp_ac_x", state: "s1", iss: "https://api.example" });
  expect(() => callbackOf(`${REDIRECT_URI}?error=access_denied&error_description=Cancelled`)).toThrow("the consent answered access_denied: Cancelled");
  expect(() => callbackOf("http://127.0.0.1:9999/callback?code=x")).toThrow(/not the registered/);
  expect(() => callbackOf(`${REDIRECT_URI}?state=s1`)).toThrow("the consent returned without an authorization code");
});

test("the client is sent to sign in once and holds its verifier only after the sign-in starts", () => {
  const provider = new MemoryOAuthProvider();
  expect(() => provider.codeVerifier()).toThrow(/no PKCE code verifier/);
  provider.redirectToAuthorization(new URL(`${WEB}/oauth/authorize?client_id=${CLIENT_ID}`));
  expect(() => provider.redirectToAuthorization(new URL(`${WEB}/oauth/authorize`))).toThrow(/a second time/);
  provider.saveCodeVerifier("verifier");
  expect(provider.codeVerifier()).toBe("verifier");
  expect(provider.clientMetadata).toMatchObject({ redirect_uris: [REDIRECT_URI], token_endpoint_auth_method: "none", scope: "read" });
  expect(provider.state()).toBe(provider.expectedState);
  expect(provider.expectedState).toMatch(/^[A-Za-z0-9_-]{32}$/);
});

test("revocation sends the token and the client id as a form", () => {
  expect(revocationBody("kvmcp_rt_a+b", CLIENT_ID)).toBe(`token=kvmcp_rt_a%2Bb&client_id=${CLIENT_ID}`);
});
