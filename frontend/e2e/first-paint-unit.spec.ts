import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import AskPage from "@/app/(protected)/ask/page";
import { drawsBeforeAccount, FIRST_PAINT_PATHS } from "@/components/AppShell";
import { AuthProvider } from "@/components/AuthProvider";
import { SIGN_IN_PREFIX, SIGNED_OUT_REDIRECT_SCRIPT } from "@/lib/signedOutRedirect";
import { signInHref } from "@/lib/sessionReturn";

import { FRONTEND } from "./moduleGraph";

test("the signed-in shell draws the ask page and the connection guide before the account is known, and no other page", () => {
  expect(FIRST_PAINT_PATHS).toEqual(["/ask", "/connect"]);
  expect(drawsBeforeAccount("/ask")).toBe(true);
  expect(drawsBeforeAccount("/connect")).toBe(true);
  for (const path of ["/settings", "/admin", "/saved", "/asked", "/ask/x", "", null]) expect(drawsBeforeAccount(path), String(path)).toBe(false);
});

test("before the account is known the ask page is drawn at rest, its heading in place and nothing pressable", () => {
  const html = renderToStaticMarkup(createElement(AuthProvider, null, createElement(AskPage)));
  expect(html).toContain('data-testid="ask-opening"');
  expect(html).toContain('inert=""');
  expect(html).toMatch(/<h1 class="font-headline text-h1 text-ink-1">What would you like to understand\?<\/h1>/);
  expect(html).toContain("Why does alum fix madder dye on cotton?");
  expect(html).not.toContain('data-testid="ask-box"');
});

function redirectedTo(cookie: string, token: string | null, path = "/ask", search = ""): string | null {
  let replaced: string | null = null;
  const location = { pathname: path, search, replace: (to: string) => (replaced = to) };
  runInNewContext(SIGNED_OUT_REDIRECT_SCRIPT, { window: { localStorage: { getItem: () => token }, location }, document: { cookie }, encodeURIComponent });
  return replaced;
}

test("a reader with no session goes to sign in before the signed-in page is drawn, and comes back to it", () => {
  expect(SIGN_IN_PREFIX).toBe("/login?next=");
  expect(redirectedTo("", null, "/ask", "?q=Why+indigo")).toBe("/login?next=%2Fask%3Fq%3DWhy%2Bindigo");
  expect(redirectedTo("", null, "/ask", "?q=Why+indigo")).toBe(signInHref("/ask?q=Why+indigo"));
  expect(redirectedTo("x-session-marker=abc", null)).toBe("/login?next=%2Fask");
  expect(redirectedTo("__Host-session-marker=; theme=dark", null, "/connect")).toBe("/login?next=%2Fconnect");
});

test("a reader who may hold a session is left to the shell, which asks the server", () => {
  expect(redirectedTo("__Host-session-marker=abc", null)).toBeNull();
  expect(redirectedTo("theme=dark; session-marker=abc", null)).toBeNull();
  expect(redirectedTo("", "a-legacy-token")).toBeNull();
  const layout = readFileSync(join(FRONTEND, "app", "(protected)", "layout.tsx"), "utf8");
  expect(layout).toMatch(/<script dangerouslySetInnerHTML=\{\{ __html: SIGNED_OUT_REDIRECT_SCRIPT \}\} \/>\s*<ConfirmProvider>/);
});

test("the ask screen still waits for its query behind a boundary that draws the same opening", () => {
  const page = readFileSync(join(FRONTEND, "app", "(protected)", "ask", "page.tsx"), "utf8");
  expect(page).toContain("<Suspense fallback={<AskOpening />}>");
  expect(page).toMatch(/if \(loading\) return <AskOpening \/>;/);
});
