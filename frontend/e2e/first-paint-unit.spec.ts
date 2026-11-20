import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import AskPage from "@/app/(protected)/ask/page";
import { drawsBeforeAccount, FIRST_PAINT_PATHS } from "@/components/AppShell";
import { AuthProvider } from "@/components/AuthProvider";

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

test("the ask screen still waits for its query behind a boundary that draws the same opening", () => {
  const page = readFileSync(join(FRONTEND, "app", "(protected)", "ask", "page.tsx"), "utf8");
  expect(page).toContain("<Suspense fallback={<AskOpening />}>");
  expect(page).toMatch(/if \(loading\) return <AskOpening \/>;/);
});
