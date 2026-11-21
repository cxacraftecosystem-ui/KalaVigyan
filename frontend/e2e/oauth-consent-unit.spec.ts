import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ClientIdentity } from "../components/oauth/ClientIdentity";
import {
  authorizationQuery,
  consentBody,
  consentProblem,
  deviceCaution,
  identityFacts,
  initialScopes,
  navigableRedirect,
  returnsToThisDevice,
  scopeList,
  TERMS_NEEDED,
  withScope
} from "../lib/oauthConsent";
import { connectionListShape, reviewShape, type AuthorizationPrompt } from "../lib/oauthContract";
import { parseShape } from "../lib/shape";

const SEARCH =
  "?response_type=code&client_id=5b1f7a9e-0000-4000-8000-000000000001&redirect_uri=https%3A%2F%2Fclaude.ai%2Fapi%2Fmcp%2Fauth_callback" +
  "&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&code_challenge_method=S256&state=xyz&scope=read+contribute+review&utm_source=mail&resource=";

const PROMPT: AuthorizationPrompt = {
  kind: "prompt",
  clientName: "Claude",
  redirectHost: "claude.ai",
  scopes: [
    { scope: "read", title: "Read", description: "Read crafts.", allowed: true, needs: null },
    { scope: "contribute", title: "Contribute", description: "Propose facts.", allowed: true, needs: null },
    { scope: "review", title: "Review", description: "Review proposals.", allowed: false, needs: "Reviewing needs a Professor." }
  ],
  terms: { version: "2026-11-19", acceptedAt: null }
};

test("the consent page forwards only the OAuth parameters the app sent", () => {
  expect(authorizationQuery(SEARCH)).toEqual({
    response_type: "code",
    client_id: "5b1f7a9e-0000-4000-8000-000000000001",
    redirect_uri: "https://claude.ai/api/mcp/auth_callback",
    code_challenge: "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
    code_challenge_method: "S256",
    state: "xyz",
    scope: "read contribute review"
  });
  expect(authorizationQuery("?client_id=abc")).toBeNull();
  expect(authorizationQuery("")).toBeNull();
});

test("every scope the role holds starts chosen, read stays chosen and a refused scope is never sent", () => {
  expect(initialScopes(PROMPT)).toEqual(["read", "contribute"]);
  expect(withScope(["read", "contribute"], "read", false)).toEqual(["read", "contribute"]);
  expect(withScope(["read", "contribute"], "contribute", false)).toEqual(["read"]);
  const query = authorizationQuery(SEARCH);
  if (!query) throw new Error("the search names its client and return address");
  expect(consentBody(query, PROMPT, ["contribute", "review"])).toEqual({
    request: query,
    scopes: ["read", "contribute"],
    termsVersion: "2026-11-19"
  });
});

test("the terms must be ticked unless this version was accepted before", () => {
  expect(consentProblem(PROMPT, false)).toBe(TERMS_NEEDED);
  expect(consentProblem(PROMPT, true)).toBeNull();
  const accepted = { ...PROMPT, terms: { version: "2026-11-19", acceptedAt: "2026-11-19T06:30:00Z" } };
  expect(consentProblem(accepted, false)).toBeNull();
});

test("the page leaves only for an app's address, never for a script", () => {
  expect(navigableRedirect("https://claude.ai/api/mcp/auth_callback?code=a&state=xyz")).toBe(true);
  expect(navigableRedirect("http://127.0.0.1:33418/callback?code=a")).toBe(true);
  expect(navigableRedirect("cursor://anysphere.cursor-retrieval/oauth/callback?code=a")).toBe(true);
  expect(navigableRedirect("javascript:alert(1)")).toBe(false);
  expect(navigableRedirect(" JavaScript:alert(1)")).toBe(false);
  expect(navigableRedirect("data:text/html,hi")).toBe(false);
  expect(navigableRedirect("/oauth/authorize")).toBe(false);
});

test("the review reply is either the prompt or a redirect, and connections list their scopes in order", () => {
  expect(parseShape(reviewShape, PROMPT)).toEqual(PROMPT);
  expect(parseShape(reviewShape, { kind: "redirect", redirectTo: "https://claude.ai/cb?error=access_denied" })).toEqual({
    kind: "redirect",
    redirectTo: "https://claude.ai/cb?error=access_denied"
  });
  expect(() => parseShape(reviewShape, { kind: "token" })).toThrow();
  const listed = parseShape(connectionListShape, {
    serverUrl: "https://api.kalavigyan.example/api/mcp",
    connections: [
      {
        id: "5b1f7a9e-0000-4000-8000-0000000000aa",
        clientName: "Claude",
        clientHost: "claude.ai",
        scopes: ["contribute", "read"],
        connectedAt: "2026-11-19T06:30:00Z",
        lastUsedAt: null
      }
    ]
  });
  expect(scopeList(listed.connections[0].scopes)).toBe("read and contribute");
  expect(scopeList(["review", "ask", "read"])).toBe("read, ask and review");
});

const PUBLISHED: AuthorizationPrompt = { ...PROMPT, clientIdHost: "claude.ai" };

test("a prompt names who publishes the app's identity, and an older reply without it still reads", () => {
  expect(parseShape(reviewShape, PUBLISHED)).toEqual(PUBLISHED);
  expect(parseShape(reviewShape, { ...PROMPT, clientIdHost: null })).toEqual({ ...PROMPT, clientIdHost: null });
  expect(parseShape(reviewShape, PROMPT)).not.toHaveProperty("clientIdHost");
  expect(identityFacts(PUBLISHED)).toEqual([
    { label: "App", value: "Claude" },
    { label: "Identity", value: "Published at claude.ai" },
    { label: "Returns you to", value: "claude.ai" },
    { label: "Asks to", value: "Read, contribute and review" }
  ]);
  expect(identityFacts(PROMPT)[1]).toEqual({ label: "Identity", value: "Registered by the app itself" });
});

test("a return to a program on this computer is cautioned, any other return is not", () => {
  for (const host of ["127.0.0.1", "127.4.5.6", "localhost", "::1", "[::1]"]) {
    expect(returnsToThisDevice({ ...PUBLISHED, redirectHost: host }), host).toBe(true);
  }
  for (const host of ["claude.ai", "127.0.0.1.example.org", "vscode.dev", "cursor:"]) {
    expect(returnsToThisDevice({ ...PUBLISHED, redirectHost: host }), host).toBe(false);
  }
  const vsCode: AuthorizationPrompt = { ...PUBLISHED, clientName: "Visual Studio Code", clientIdHost: "vscode.dev", redirectHost: "127.0.0.1" };
  expect(deviceCaution(vsCode)).toBe("This sign-in returns to a program on this computer. Approve it only if you started it from Visual Studio Code here.");
  const cautioned = renderToStaticMarkup(createElement(ClientIdentity, { prompt: vsCode }));
  expect(cautioned).toContain("Published at vscode.dev");
  expect(cautioned).toContain('data-testid="device-caution"');
  expect(renderToStaticMarkup(createElement(ClientIdentity, { prompt: PUBLISHED }))).not.toContain('data-testid="device-caution"');
});
