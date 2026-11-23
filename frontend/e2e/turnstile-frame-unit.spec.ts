import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { CONTENT_SECURITY_POLICY, TURNSTILE_SOURCE } from "../next.config";

const WIDGET = readFileSync(join(__dirname, "..", "components", "auth", "TurnstileWidget.tsx"), "utf8");

function directive(policy: string, name: string): string[] {
  const found = policy.split(";").map((part) => part.trim()).find((part) => part.startsWith(`${name} `));
  return found ? found.split(/\s+/).slice(1) : [];
}

test("the policy lets the sign-up page frame the Turnstile challenge it loads", () => {
  const script = /SCRIPT_SRC = "([^"]+)"/.exec(WIDGET)?.[1] ?? "";
  expect(new URL(script).origin).toBe(TURNSTILE_SOURCE);
  expect(directive(CONTENT_SECURITY_POLICY, "frame-src")).toContain(TURNSTILE_SOURCE);
});

test("the frame policy still names only the sign-in frames it needs", () => {
  expect(directive(CONTENT_SECURITY_POLICY, "frame-src")).toEqual(["https://accounts.google.com/gsi/", "https://challenges.cloudflare.com"]);
  expect(directive(CONTENT_SECURITY_POLICY, "frame-ancestors")).toEqual(["'none'"]);
});
