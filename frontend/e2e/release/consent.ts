import { expect, type Page } from "@playwright/test";

import { settle } from "../production/capture";
import type { Credentials } from "../production/run";
import { submitSignIn } from "../production/signIn";

import { SIGN_IN_PATH } from "./keyPages";

export const CONSENT_PATH = "/oauth/authorize";
export const APPROVE_PATH = "/api/oauth/authorize/approve";

const CONSENT_TIMEOUT_MS = 60_000;
const CONSENT_FORM = "consent-form";
const RETURNED = "<!doctype html><title>Signed in</title><p>Signed in.</p>";

type Refusal = { detail?: unknown };

async function consentShown(page: Page): Promise<void> {
  const form = page.getByTestId(CONSENT_FORM);
  const alert = page.locator("main").getByRole("alert");
  await expect(form.or(alert).first()).toBeVisible({ timeout: CONSENT_TIMEOUT_MS });
  if (!(await form.isVisible())) throw new Error(`the consent page refused the request: ${await alert.first().innerText()}`);
}

async function signInIfAsked(page: Page, account: Credentials): Promise<void> {
  const form = page.getByTestId(CONSENT_FORM);
  const alert = page.locator("main").getByRole("alert");
  await expect(form.or(alert).or(page.getByLabel("Password", { exact: true })).first()).toBeVisible({ timeout: CONSENT_TIMEOUT_MS });
  if (new URL(page.url()).pathname !== SIGN_IN_PATH) return;
  await settle(page);
  await submitSignIn(page, account);
  await page.waitForURL((url) => url.pathname === CONSENT_PATH, { timeout: CONSENT_TIMEOUT_MS });
}

async function acceptTermsIfAsked(page: Page): Promise<boolean> {
  const terms = page.getByTestId("terms-of-use");
  if ((await terms.count()) === 0) return false;
  const box = terms.getByRole("checkbox");
  await expect(box).toBeEnabled({ timeout: CONSENT_TIMEOUT_MS });
  await box.check();
  return true;
}

async function approved(page: Page, returnOrigin: string): Promise<string> {
  const returning = page.waitForRequest((request) => new URL(request.url()).origin === returnOrigin, { timeout: CONSENT_TIMEOUT_MS });
  returning.catch(() => undefined);
  const answered = page.waitForResponse((response) => new URL(response.url()).pathname === APPROVE_PATH && response.request().method() === "POST", { timeout: CONSENT_TIMEOUT_MS });
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  const response = await answered;
  if (!response.ok()) {
    const body = (await response.json()) as Refusal;
    throw new Error(`Approve answered ${response.status()}: ${typeof body.detail === "string" ? body.detail : "no detail"}`);
  }
  return (await returning).url();
}

export async function approveInBrowser(page: Page, authorizationUrl: URL, account: Credentials, redirectUri: string): Promise<{ redirectTo: string; acceptedTerms: boolean }> {
  const returnOrigin = new URL(redirectUri).origin;
  await page.route((url) => url.origin === returnOrigin, (route) => route.fulfill({ status: 200, contentType: "text/html", body: RETURNED }));
  await page.goto(authorizationUrl.href, { waitUntil: "domcontentloaded" });
  await signInIfAsked(page, account);
  await consentShown(page);
  const acceptedTerms = await acceptTermsIfAsked(page);
  return { redirectTo: await approved(page, returnOrigin), acceptedTerms };
}
