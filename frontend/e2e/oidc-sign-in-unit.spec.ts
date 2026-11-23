import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { NextRequest } from "next/server";

import { GET as callbackRoute } from "@/app/login/callback/route";
import {
  PENDING_KEY,
  PENDING_LIFETIME_MS,
  authorizeUrl,
  beginSignIn,
  callbackErrorMessage,
  callbackTarget,
  configuredOidcProviders,
  fetchOidcNonce,
  loginBody,
  microsoftTenant,
  parseCallbackFragment,
  sha256Base64Url,
  takePendingSignIn,
  type PendingSignIn
} from "@/lib/oidcSignIn";
import { rememberSignInReturn, signInReturnOnce, takeSignInReturn } from "@/lib/sessionReturn";
import { CONTENT_SECURITY_POLICY } from "../next.config";

const read = (...parts: string[]) => readFileSync(join(__dirname, "..", ...parts), "utf8");
const LOGIN = read("app", "login", "page.tsx");
const BUTTONS = read("components", "auth", "OidcSignInButtons.tsx");
const HOOK = read("components", "auth", "useOidcSignIn.ts");

const SERVER_NONCE = "server-issued-nonce-0123456789abcdefghijklmnopq";
const WEB = "https://kalavigyan.vercel.app";

class MemoryStorage {
  values = new Map<string, string>();
  getItem(key: string) {
    return this.values.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.values.set(key, value);
  }
  removeItem(key: string) {
    this.values.delete(key);
  }
}

const pendingIn = (storage: MemoryStorage) => JSON.parse(storage.getItem(PENDING_KEY) ?? "{}") as PendingSignIn;

function onLoginPage<T>(search: string, sessionStorage: MemoryStorage, run: () => T): T {
  const holder = globalThis as unknown as { window?: unknown };
  const before = holder.window;
  holder.window = { location: { search }, sessionStorage };
  try {
    return run();
  } finally {
    holder.window = before;
  }
}

test("no client ID, no button", () => {
  expect(configuredOidcProviders({})).toEqual([]);
  expect(configuredOidcProviders({ microsoftClientId: "  ", yahooClientId: "" })).toEqual([]);
});

test("a Yahoo client ID alone draws Yahoo and leaves Microsoft hidden", () => {
  const providers = configuredOidcProviders({ yahooClientId: " y-id " });
  expect(providers.map((p) => [p.id, p.label, p.clientId])).toEqual([["YAHOO", "Yahoo", "y-id"]]);
  expect(providers[0].authorizeEndpoint).toBe("https://api.login.yahoo.com/oauth2/request_auth");
});

test("each configured provider is offered, Microsoft first", () => {
  const providers = configuredOidcProviders({ microsoftClientId: "ms-id", yahooClientId: "y-id" });
  expect(providers.map((p) => p.id)).toEqual(["MICROSOFT", "YAHOO"]);
  expect(providers[0].authorizeEndpoint).toBe("https://login.microsoftonline.com/common/oauth2/v2.0/authorize");
});

test("the Microsoft tenant is a keyword or a tenant ID, and anything else hides the button", () => {
  expect(microsoftTenant(undefined)).toBe("common");
  expect(microsoftTenant("Organizations")).toBe("organizations");
  expect(microsoftTenant("72F988BF-86F1-41AF-91AB-2D7CD011DB47")).toBe("72f988bf-86f1-41af-91ab-2d7cd011db47");
  expect(microsoftTenant("contoso.onmicrosoft.com")).toBeNull();
  expect(configuredOidcProviders({ microsoftClientId: "ms-id", microsoftTenant: "contoso.com" })).toEqual([]);
});

test("the login page draws the buttons only from configuration, with no placeholder", () => {
  expect(LOGIN).toContain("useOidcSignIn(");
  expect(LOGIN).toMatch(/<OidcSignInButtons\s+providers=\{oidc\.providers\}/);
  expect(LOGIN).toContain("google.clientId || oidc.providers.length > 0 ? <OrDivider />");
  expect(HOOK).toContain("configuredOidcProviders()");
  expect(BUTTONS).toContain("if (providers.length === 0) return null;");
  expect(BUTTONS).toContain("Continue with {provider.label}");
  expect(`${LOGIN}${BUTTONS}`).not.toMatch(/coming soon/i);
});

test("the request carries PKCE S256 and the digest of the server's nonce, never the raw values", async () => {
  const storage = new MemoryStorage();
  const [yahoo] = configuredOidcProviders({ yahooClientId: "y-id" });
  const url = new URL(await beginSignIn(yahoo, WEB, { rawNonce: SERVER_NONCE, storage }));
  const pending = pendingIn(storage);
  expect(url.origin + url.pathname).toBe("https://api.login.yahoo.com/oauth2/request_auth");
  expect(url.searchParams.get("response_type")).toBe("code");
  expect(url.searchParams.get("code_challenge_method")).toBe("S256");
  expect(url.searchParams.get("redirect_uri")).toBe("https://kalavigyan.vercel.app/login/callback");
  expect(url.searchParams.get("code_challenge")).toBe(await sha256Base64Url(pending.codeVerifier));
  expect(url.searchParams.get("nonce")).toBe(await sha256Base64Url(SERVER_NONCE));
  expect(pending.rawNonce).toBe(SERVER_NONCE);
  expect(url.toString()).not.toContain(pending.codeVerifier);
  expect(url.toString()).not.toContain(SERVER_NONCE);
  expect(pending.state.startsWith("web.")).toBe(true);
  expect(pending.codeVerifier.length).toBeGreaterThanOrEqual(43);
});

test("the sha-256 digest is base64url without padding (RFC 7636 appendix B)", async () => {
  expect(await sha256Base64Url("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")).toBe(
    "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
  );
});

test("Yahoo is asked for a code with no Microsoft-only parameters", () => {
  const [yahoo] = configuredOidcProviders({ yahooClientId: "y-id" });
  const url = new URL(authorizeUrl(yahoo, { redirectUri: `${WEB}/login/callback`, state: "web.s", codeChallenge: "c", nonceDigest: "n" }));
  expect(url.searchParams.get("client_id")).toBe("y-id");
  expect(url.searchParams.get("scope")).toBe("openid email profile");
  expect(url.searchParams.has("response_mode")).toBe(false);
  expect(url.searchParams.has("prompt")).toBe(false);
});

test("the nonce is asked of our own API for the chosen provider", async () => {
  const calls: { url: string; body: string }[] = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    calls.push({ url: String(input), body: String(init?.body) });
    return new Response(JSON.stringify({ nonce: SERVER_NONCE }), { headers: { "content-type": "application/json" } });
  };
  try {
    expect(await fetchOidcNonce("YAHOO")).toBe(SERVER_NONCE);
  } finally {
    globalThis.fetch = realFetch;
  }
  expect(calls).toEqual([{ url: "/api/auth/oidc/nonce", body: JSON.stringify({ provider: "YAHOO" }) }]);
});

test("the sign-in body carries the raw nonce and the verifier to our own route only", () => {
  const pending: PendingSignIn = {
    provider: "YAHOO",
    state: "web.s",
    codeVerifier: "v".repeat(64),
    rawNonce: SERVER_NONCE,
    redirectUri: `${WEB}/login/callback`,
    startedAt: 0
  };
  expect(loginBody(pending, "the-code")).toEqual({
    oidcProvider: "YAHOO",
    oidcCode: "the-code",
    oidcCodeVerifier: "v".repeat(64),
    oidcRedirectUri: "https://kalavigyan.vercel.app/login/callback",
    oidcNonce: SERVER_NONCE
  });
});

test("a callback for another state, a second read, or a stale sign-in completes nothing", async () => {
  const storage = new MemoryStorage();
  const [yahoo] = configuredOidcProviders({ yahooClientId: "y-id" });
  await beginSignIn(yahoo, WEB, { rawNonce: SERVER_NONCE, storage });
  const state = pendingIn(storage).state;
  expect(takePendingSignIn("web.somebody-else", storage)).toBeNull();
  expect(takePendingSignIn(state, storage)).toBeNull();

  await beginSignIn(yahoo, WEB, { rawNonce: SERVER_NONCE, storage });
  const stale = pendingIn(storage);
  expect(takePendingSignIn(stale.state, storage, stale.startedAt + PENDING_LIFETIME_MS + 1)).toBeNull();

  await beginSignIn(yahoo, WEB, { rawNonce: SERVER_NONCE, storage });
  const current = pendingIn(storage);
  expect(takePendingSignIn(current.state, storage)?.provider).toBe("YAHOO");
  expect(takePendingSignIn(current.state, storage)).toBeNull();
});

test("a cancelled or failed return reads like the Google refusals", () => {
  expect(callbackErrorMessage("YAHOO", "access_denied")).toBe("Yahoo sign-in was cancelled.");
  expect(callbackErrorMessage("YAHOO", "server_error")).toBe("Yahoo sign-in didn't work. Try again.");
});

test("a web state goes back to /login in the fragment, with nothing but code, state and error", () => {
  const target = callbackTarget(new URLSearchParams("code=abc&state=web.s1&session_state=zzz&iss=x"));
  expect(target).toBe("/login#oidc=code%3Dabc%26state%3Dweb.s1");
  expect(parseCallbackFragment(target.slice("/login".length))).toEqual({ code: "abc", state: "web.s1", error: null });
});

test("no state hands the code to an app scheme, because KalaVigyan is web only", () => {
  expect(callbackTarget(new URLSearchParams("code=abc&state=app.s2"))).toBe("/login#oidc=code%3Dabc%26state%3Dapp.s2");
  expect(callbackTarget(new URLSearchParams("code=abc&state=pw.s4")).startsWith("/settings#oidc=")).toBe(true);
});

test("the callback route redirects within the site, uncached and without a Referer", async () => {
  const response = callbackRoute(new NextRequest(`${WEB}/login/callback?code=abc&state=web.s1&iss=x`));
  expect(response.status).toBe(302);
  expect(response.headers.get("location")).toBe(`${WEB}/login#oidc=code%3Dabc%26state%3Dweb.s1`);
  expect(response.headers.get("cache-control")).toBe("no-store");
  expect(response.headers.get("referrer-policy")).toBe("no-referrer");
  const cancelled = callbackRoute(new NextRequest(`${WEB}/login/callback?error=access_denied&state=web.s2`));
  expect(cancelled.headers.get("location")).toBe(`${WEB}/login#oidc=state%3Dweb.s2%26error%3Daccess_denied`);
});

test("the page strips the answer off the address bar before using it", () => {
  const from = HOOK.indexOf("parseCallbackFragment(window.location.hash)");
  expect(from).toBeGreaterThan(-1);
  const replaced = HOOK.indexOf("window.history.replaceState", from);
  expect(replaced).toBeGreaterThan(from);
  expect(replaced).toBeLessThan(HOOK.indexOf("takePendingSignIn(", from));
});

test("the browser never talks to Yahoo, so the policy names no Yahoo host", () => {
  expect(CONTENT_SECURITY_POLICY).not.toMatch(/yahoo/i);
});

test("a Yahoo or Microsoft sign-in lands on the page it was asked from, however often the login page asks where to go", () => {
  const asked = "/oauth/authorize?client_id=claude&redirect_uri=https%3A%2F%2Fclaude.ai%2Fapi%2Fmcp%2Fauth_callback";
  const storage = new MemoryStorage();
  onLoginPage(`?next=${encodeURIComponent(asked)}`, storage, () => rememberSignInReturn(`?next=${encodeURIComponent(asked)}`));
  const stored = new Map(storage.values);
  const landings = onLoginPage("", storage, () => {
    const landing = signInReturnOnce();
    return [landing(), landing()];
  });
  expect(landings).toEqual([asked, asked]);
  storage.values = stored;
  expect(onLoginPage("", storage, () => [takeSignInReturn(), takeSignInReturn()])).toEqual([asked, "/ask"]);
  expect(LOGIN).not.toContain("takeSignInReturn(");
  expect(LOGIN.match(/router\.replace\(landing\(\)\)/g)).toHaveLength(4);
});
