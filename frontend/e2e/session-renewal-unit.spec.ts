import { expect, test } from "@playwright/test";
import { NextRequest } from "next/server";

import { POST as renewRoute } from "@/app/api/session/renew/route";
import { renewalDue, renewedCookieLines, SESSION_RENEW_AFTER_SECONDS, tokenLifetimeSeconds } from "@/lib/server/apiProxy";
import { getSessionMarker, renewSession, RENEWAL_CHECK_MS, resetSessionStateForTests } from "@/lib/session";
import { SESSION_COOKIE, SESSION_MARKER_COOKIE, SESSION_RENEW_PATH } from "@/lib/sessionCookie";
import { proxy } from "@/proxy";

const WEB = "https://kalavigyan.example";
const API = "https://api.kalavigyan.example";
const DAY = 24 * 60 * 60;
const YEAR = 365 * DAY;
const MARKER = "first-marker";

type Claims = { sid?: string; iat: number; exp: number };

function nowSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

function tokenOf(claims: Claims): string {
  return `head.${Buffer.from(JSON.stringify({ sub: "u1", tv: 0, ...claims })).toString("base64url")}.signature`;
}

function claimsOf(token: string): Claims {
  return JSON.parse(Buffer.from(token.split(".")[1] ?? "", "base64url").toString("utf8")) as Claims;
}

function issued(daysAgo: number): string {
  const iat = nowSeconds() - Math.round(daysAgo * DAY);
  return tokenOf({ sid: "s1", iat, exp: iat + YEAR });
}

class Api {
  renewals = 0;
  refuse = false;

  serve(url: string, headers: Headers): Response {
    if (new URL(url).pathname !== "/api/auth/renew") return new Response("{}", { status: 404 });
    this.renewals += 1;
    if (this.refuse) return new Response(JSON.stringify({ detail: "This session is no longer valid. Sign in again." }), { status: 401 });
    const presented = claimsOf((headers.get("authorization") ?? "").replace(/^Bearer /, ""));
    const iat = nowSeconds();
    const token = tokenOf({ sid: presented.sid ?? "s-new", iat, exp: iat + YEAR });
    return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json", "X-Session-Token": token } });
  }
}

class Browser {
  jar = new Map<string, string>();
  lines: string[] = [];
  asked = 0;

  constructor(token: string | null) {
    if (token) {
      this.jar.set(SESSION_COOKIE, encodeURIComponent(token));
      this.jar.set(SESSION_MARKER_COOKIE, MARKER);
    }
  }

  cookieHeader(): string {
    return [...this.jar].map(([name, value]) => `${name}=${value}`).join("; ");
  }

  token(): string {
    return decodeURIComponent(this.jar.get(SESSION_COOKIE) ?? "");
  }

  keep(response: Response): void {
    for (const line of response.headers.getSetCookie()) {
      this.lines.push(line);
      const [pair] = line.split(";");
      this.jar.set(pair.slice(0, pair.indexOf("=")), pair.slice(pair.indexOf("=") + 1));
    }
  }
}

function site(api: Api, browser: Browser): typeof fetch {
  return async (input, init) => {
    const url = String(input);
    if (url.startsWith(API)) return api.serve(url, new Headers(init?.headers));
    browser.asked += 1;
    const headers = new Headers(init?.headers);
    headers.set("cookie", browser.cookieHeader());
    headers.set("sec-fetch-site", "same-origin");
    const request = new NextRequest(new URL(url, WEB), { method: init?.method ?? "GET", headers });
    const decided = proxy(request);
    expect(decided.headers.get("x-middleware-next")).toBe("1");
    const response = await renewRoute(request);
    browser.keep(response);
    return response;
  };
}

async function inPage<T>(api: Api, browser: Browser, run: () => Promise<T>): Promise<T> {
  const holder = globalThis as unknown as { window?: unknown; document?: unknown; fetch: typeof fetch };
  const saved = { window: holder.window, document: holder.document, fetch: holder.fetch, origin: process.env.API_ORIGIN };
  process.env.API_ORIGIN = API;
  holder.fetch = site(api, browser);
  holder.document = { get cookie() { return browser.jar.has(SESSION_MARKER_COOKIE) ? `${SESSION_MARKER_COOKIE}=${browser.jar.get(SESSION_MARKER_COOKIE)}` : ""; } };
  holder.window = { location: { pathname: "/craft/kutch-ajrakh", search: "" } };
  resetSessionStateForTests();
  try {
    return await run();
  } finally {
    Object.assign(holder, { window: saved.window, document: saved.document, fetch: saved.fetch });
    if (saved.origin === undefined) delete process.env.API_ORIGIN;
    else process.env.API_ORIGIN = saved.origin;
  }
}

test("a session last renewed over a day ago is renewed for a year on the next visit, its cookie kept as strict as before", async () => {
  const api = new Api();
  const browser = new Browser(issued(2));
  await inPage(api, browser, () => renewSession());
  expect(api.renewals).toBe(1);
  const renewed = claimsOf(browser.token());
  expect(renewed.sid).toBe("s1");
  expect(Math.abs(renewed.exp - (nowSeconds() + YEAR))).toBeLessThanOrEqual(5);
  const [session, marker] = browser.lines;
  expect(session).toContain(`${SESSION_COOKIE}=`);
  for (const attribute of ["HttpOnly", "Secure", "SameSite=Lax", "Path=/"]) expect(session).toContain(attribute);
  const maxAge = Number(/Max-Age=(\d+)/.exec(session)?.[1]);
  expect(Math.abs(maxAge - YEAR)).toBeLessThanOrEqual(5);
  expect(marker).toBe(`${SESSION_MARKER_COOKIE}=${MARKER}; Path=/; Max-Age=${maxAge}; SameSite=Lax; Secure`);
  expect(browser.jar.get(SESSION_MARKER_COOKIE)).toBe(MARKER);
});

test("a session renewed within the day is left as it is and the API is not asked", async () => {
  const api = new Api();
  const token = issued(0.5);
  const browser = new Browser(token);
  await inPage(api, browser, () => renewSession());
  expect(browser.asked).toBe(1);
  expect(api.renewals).toBe(0);
  expect(browser.lines).toEqual([]);
  expect(browser.token()).toBe(token);
});

test("a session from before session ids is renewed at once into one that has an id", async () => {
  const api = new Api();
  const iat = nowSeconds() - 600;
  const browser = new Browser(tokenOf({ iat, exp: iat + 7 * DAY }));
  await inPage(api, browser, () => renewSession());
  expect(api.renewals).toBe(1);
  expect(claimsOf(browser.token()).sid).toBe("s-new");
});

test("a renewal the API refuses changes no cookie and signs no one out from the page", async () => {
  const api = new Api();
  api.refuse = true;
  const token = issued(3);
  const browser = new Browser(token);
  await inPage(api, browser, async () => {
    await renewSession();
    expect(getSessionMarker()).toBe(MARKER);
  });
  expect(api.renewals).toBe(1);
  expect(browser.lines).toEqual([]);
  expect(browser.token()).toBe(token);
});

test("the page asks at most once an hour, and never without a session", async () => {
  const api = new Api();
  const browser = new Browser(issued(0.2));
  await inPage(api, browser, async () => {
    await renewSession(1_000);
    await renewSession(1_000 + RENEWAL_CHECK_MS - 1);
    expect(browser.asked).toBe(1);
    await renewSession(1_000 + RENEWAL_CHECK_MS);
    expect(browser.asked).toBe(2);
  });
  const signedOut = new Browser(null);
  await inPage(api, signedOut, () => renewSession());
  expect(signedOut.asked).toBe(0);
});

test("a renewal asked from another site is refused before the API is reached", async () => {
  const api = new Api();
  const browser = new Browser(issued(5));
  await inPage(api, browser, async () => {
    const request = new NextRequest(new URL(SESSION_RENEW_PATH, WEB), {
      method: "POST",
      headers: { cookie: browser.cookieHeader(), "sec-fetch-site": "cross-site" }
    });
    expect((await renewRoute(request)).status).toBe(403);
  });
  expect(api.renewals).toBe(0);
});

test("a renewal falls due a day after the token was issued, or at once for a token without a session id", () => {
  const now = 1_800_000_000_000;
  const at = (secondsAgo: number, sid?: string) => tokenOf({ sid, iat: now / 1000 - secondsAgo, exp: now / 1000 + YEAR });
  expect(renewalDue(at(SESSION_RENEW_AFTER_SECONDS, "s1"), now)).toBe(true);
  expect(renewalDue(at(SESSION_RENEW_AFTER_SECONDS - 1, "s1"), now)).toBe(false);
  expect(renewalDue(at(60), now)).toBe(true);
  expect(renewalDue("not-a-token", now)).toBe(false);
  expect(SESSION_RENEW_AFTER_SECONDS).toBe(86_400);
});

test("a renewed cookie lives as long as its token and keeps the marker it was given", () => {
  const now = 1_800_000_000_000;
  const token = tokenOf({ sid: "s1", iat: now / 1000, exp: now / 1000 + YEAR });
  expect(tokenLifetimeSeconds(token, now)).toBe(31_536_000);
  expect(renewedCookieLines(token, "kept", true, now)).toEqual([
    `${SESSION_COOKIE}=${encodeURIComponent(token)}; Path=/; Max-Age=31536000; SameSite=Lax; Secure; HttpOnly`,
    `${SESSION_MARKER_COOKIE}=kept; Path=/; Max-Age=31536000; SameSite=Lax; Secure`
  ]);
  expect(tokenLifetimeSeconds("not-a-token", now)).toBe(7 * DAY);
});
