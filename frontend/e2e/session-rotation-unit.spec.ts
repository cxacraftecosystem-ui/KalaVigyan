import { expect, test } from "@playwright/test";
import { NextRequest } from "next/server";

import { POST as accountWrite } from "@/app/api/auth/[...path]/route";
import { POST as endSessionRoute } from "@/app/api/session/end/route";
import { accountStepFor } from "@/lib/accountGate";
import { apiFetch } from "@/lib/api";
import { getSessionMarker, resetSessionStateForTests } from "@/lib/session";
import { SESSION_COOKIE, SESSION_MARKER_COOKIE } from "@/lib/sessionCookie";
import { fetchTwoFactorStatus } from "@/lib/twoFactor";
import { answerTwoStepCode, readsAccountNow } from "@/lib/twoStepFlow";
import type { User } from "@/lib/types";
import { proxy } from "@/proxy";

const WEB = "https://kalavigyan.example";
const API = "https://api.kalavigyan.example";
const RECOVERY_CODES = ["a1b2c3d4", "e5f6g7h8", "j9k8m7n6", "p5q4r3s2", "t1u2v3w4", "x5y6z7a8", "b9c8d7e6", "f5g4h3j2", "k1m2n3p4", "q5r6s7t8"];
const ENDED = "This session is no longer valid. Sign in again.";

function tokenOf(version: number): string {
  const claims = Buffer.from(JSON.stringify({ tv: version, exp: Math.floor(Date.now() / 1000) + 3600 })).toString("base64url");
  return `head.${claims}.signature`;
}

function versionOf(token: string): number | null {
  try {
    const claims = JSON.parse(Buffer.from(token.split(".")[1] ?? "", "base64url").toString("utf8")) as { tv?: unknown };
    return typeof claims.tv === "number" ? claims.tv : null;
  } catch {
    return null;
  }
}

function answer(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });
}

class Account {
  version = 0;
  enabled = false;

  user(): User {
    return { id: "u1", email: "meera@iitkgp.ac.in", name: "Meera", role: "PROFESSOR", twoFactorRequired: true, twoFactorEnabled: this.enabled };
  }

  rotated(body: Record<string, unknown>): Response {
    this.version += 1;
    const token = tokenOf(this.version);
    return answer(200, { ...body, accessToken: token }, { "X-Session-Token": token });
  }

  serve(url: string, headers: Headers): Response {
    const bearer = (headers.get("authorization") ?? "").replace(/^Bearer /, "");
    if (versionOf(bearer) !== this.version) return answer(401, { detail: ENDED });
    const path = new URL(url).pathname;
    if (path === "/api/me") return answer(200, this.user());
    if (path === "/api/auth/two-factor") return answer(200, { enabled: this.enabled, pending: false, recovery_codes_remaining: this.enabled ? 10 : 0, enabled_at: null });
    if (path === "/api/auth/two-factor/enable") {
      this.enabled = true;
      return this.rotated({ recovery_codes: RECOVERY_CODES });
    }
    if (path === "/api/auth/two-factor/disable") {
      this.enabled = false;
      return this.rotated({ ok: true });
    }
    return answer(404, { detail: "Not Found" });
  }
}

class Browser {
  jar = new Map<string, string>();
  leftFor: string[] = [];
  seen: { headers: Headers; text: string }[] = [];

  constructor(token: string) {
    this.jar.set(SESSION_COOKIE, encodeURIComponent(token));
    this.jar.set(SESSION_MARKER_COOKIE, "first-marker");
  }

  cookieHeader(): string {
    return [...this.jar].map(([name, value]) => `${name}=${value}`).join("; ");
  }

  sessionToken(): string {
    return decodeURIComponent(this.jar.get(SESSION_COOKIE) ?? "");
  }

  keep(response: Response): void {
    for (const line of response.headers.getSetCookie()) {
      const [pair, ...attributes] = line.split(";").map((part) => part.trim());
      const [name, value] = [pair.slice(0, pair.indexOf("=")), pair.slice(pair.indexOf("=") + 1)];
      if (!value || attributes.includes("Max-Age=0")) this.jar.delete(name);
      else this.jar.set(name, value);
    }
  }
}

function forwardedBy(decided: Response): Headers {
  const headers = new Headers();
  const authorization = decided.headers.get("x-middleware-request-authorization");
  if (authorization) headers.set("authorization", authorization);
  return headers;
}

async function answeredByTheWeb(request: NextRequest): Promise<Response> {
  if (request.nextUrl.pathname === "/api/session/end") return endSessionRoute(request);
  return accountWrite(request);
}

function site(account: Account, browser: Browser): typeof fetch {
  return async (input, init) => {
    const url = String(input);
    if (url.startsWith(API)) return account.serve(url, new Headers(init?.headers));
    const headers = new Headers(init?.headers);
    headers.set("cookie", browser.cookieHeader());
    headers.set("sec-fetch-site", "same-origin");
    const request = new NextRequest(new URL(url, WEB), { method: init?.method ?? "GET", headers, body: init?.body ?? undefined });
    const decided = proxy(request);
    let response: Response = decided;
    if (decided.headers.get("x-middleware-next") === "1") response = await answeredByTheWeb(request);
    else if (decided.headers.get("x-middleware-rewrite")) response = account.serve(decided.headers.get("x-middleware-rewrite") ?? "", forwardedBy(decided));
    browser.keep(response);
    browser.seen.push({ headers: response.headers, text: await response.clone().text() });
    return response;
  };
}

async function onSettings<T>(account: Account, browser: Browser, run: () => Promise<T>): Promise<T> {
  const holder = globalThis as unknown as { window?: unknown; document?: unknown; fetch: typeof fetch };
  const saved = { window: holder.window, document: holder.document, fetch: holder.fetch, origin: process.env.API_ORIGIN };
  process.env.API_ORIGIN = API;
  holder.fetch = site(account, browser);
  holder.document = { get cookie() { return `${SESSION_MARKER_COOKIE}=${browser.jar.get(SESSION_MARKER_COOKIE) ?? ""}`; } };
  holder.window = { location: { pathname: "/settings", search: "", replace: (href: string) => browser.leftFor.push(href) } };
  resetSessionStateForTests();
  try {
    return await run();
  } finally {
    Object.assign(holder, { window: saved.window, document: saved.document, fetch: saved.fetch });
    if (saved.origin === undefined) delete process.env.API_ORIGIN;
    else process.env.API_ORIGIN = saved.origin;
  }
}

function pageScriptSawNoToken(browser: Browser): void {
  for (const { headers, text } of browser.seen) {
    expect(headers.get("x-session-token")).toBeNull();
    expect(text).not.toContain("accessToken");
    expect(text).not.toContain("head.");
  }
}

test("a write under /api/auth is relayed by the web, and every other call is rewritten to the API with the session", async () => {
  const decide = (method: string, path: string) => proxy(new NextRequest(`${WEB}${path}`, { method, headers: { "sec-fetch-site": "same-origin" } }));
  await onSettings(new Account(), new Browser(tokenOf(0)), async () => {
    for (const path of ["/api/auth/two-factor/enable", "/api/auth/two-factor/disable", "/api/auth/change-password", "/api/auth/login", "/api/auth/two-factor/setup/cancel"]) {
      expect(decide("POST", path).headers.get("x-middleware-next"), path).toBe("1");
    }
    expect(decide("GET", "/api/version").headers.get("x-middleware-next")).toBe("1");
    expect(decide("GET", "/api/auth/two-factor").headers.get("x-middleware-rewrite")).toBe(`${API}/api/auth/two-factor`);
    expect(decide("POST", "/api/answers/stream").headers.get("x-middleware-rewrite")).toBe(`${API}/api/answers/stream`);
  });
});

test("turning two-step verification on keeps the session and the recovery codes, and turning it off keeps the session", async () => {
  const account = new Account();
  const browser = new Browser(tokenOf(0));
  await onSettings(account, browser, async () => {
    const before = await apiFetch<User>("/me");
    expect(accountStepFor(before)).toBe("two-step");

    const on = await answerTwoStepCode("setup", "123456");
    expect(on).toEqual({ kind: "codes", codes: RECOVERY_CODES });
    expect(readsAccountNow(on)).toBe(false);
    expect(versionOf(browser.sessionToken())).toBe(1);
    expect((await fetchTwoFactorStatus()).enabled).toBe(true);
    expect(browser.leftFor).toEqual([]);
    expect(getSessionMarker()).not.toBe("first-marker");
    expect(getSessionMarker()).not.toBeNull();

    const after = await apiFetch<User>("/me", {}, { redirectOn401: false });
    expect(after.twoFactorEnabled).toBe(true);
    expect(accountStepFor(after)).toBeNull();

    const off = await answerTwoStepCode("disable", "654321");
    expect(off).toEqual({ kind: "off" });
    expect(readsAccountNow(off)).toBe(true);
    expect(versionOf(browser.sessionToken())).toBe(2);
    expect((await apiFetch<User>("/me", {}, { redirectOn401: false })).twoFactorEnabled).toBe(false);
    expect((await fetchTwoFactorStatus()).enabled).toBe(false);
    expect(browser.leftFor).toEqual([]);
  });
  pageScriptSawNoToken(browser);
});

test("a session the API no longer accepts still ends, so the take-over is not a way around a revoked token", async () => {
  const account = new Account();
  account.version = 3;
  const browser = new Browser(tokenOf(2));
  await onSettings(account, browser, async () => {
    await expect(fetchTwoFactorStatus()).rejects.toThrow(ENDED);
    expect(browser.leftFor).toEqual(["/session-ended?next=%2Fsettings"]);
    await expect(answerTwoStepCode("setup", "123456")).rejects.toThrow(ENDED);
    expect(account.enabled).toBe(false);
  });
});
