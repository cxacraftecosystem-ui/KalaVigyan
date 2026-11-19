import { expect, test } from "@playwright/test";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { Pagination } from "@/components/Pagination";
import { accountFacts, signInFacts } from "@/components/settings/accountFactList";
import { hasStoredOverride, maskedValue } from "@/components/settings/managedSecrets";
import { contrastLine, motionLine, textLine, themeLine } from "@/components/settings/preferenceLines";
import { returnsFromConfirmation, settingsHref, settingsTab } from "@/components/settings/settingsTabs";
import { StatusBadge } from "@/components/StatusBadge";
import { applyPreferences, contrastIsHigh, DEFAULT_PREFERENCES, normalizePreferences, PREFERENCES_BOOT_SCRIPT, PREFERENCES_KEY, type Preferences } from "@/lib/preferences";
import type { User } from "@/lib/types";

const html = (element: ReactElement) => renderToStaticMarkup(element);
const words = (markup: string) => markup.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();

function bootAttributes(stored: unknown): Record<string, string> {
  const written: Record<string, string> = {};
  const root = { setAttribute: (name: string, value: string) => (written[name] = value) };
  const fakeWindow = {
    localStorage: { getItem: (key: string) => (key === PREFERENCES_KEY ? JSON.stringify(stored) : null) },
    matchMedia: () => ({ matches: false })
  };
  new Function("document", "window", PREFERENCES_BOOT_SCRIPT)({ documentElement: root }, fakeWindow);
  return written;
}

function appliedAttributes(preferences: Preferences): Record<string, string> {
  const written: Record<string, string> = {};
  const root = { setAttribute: (name: string, value: string) => (written[name] = value), removeAttribute: (name: string) => delete written[name] };
  const holder = globalThis as unknown as { document?: unknown };
  const before = holder.document;
  holder.document = { documentElement: root, querySelectorAll: () => [] };
  try {
    applyPreferences(preferences);
  } finally {
    holder.document = before;
  }
  return written;
}

const READER: User = { id: "u1", email: "ananya@iitkgp.ac.in", name: "Ananya", role: "RESEARCHER" };

test("the contrast preference has three states, and an old on or off reads as high or the device", () => {
  expect(DEFAULT_PREFERENCES.highContrast).toBe("system");
  expect(normalizePreferences({}).highContrast).toBe("system");
  expect(normalizePreferences({ highContrast: true }).highContrast).toBe("high");
  expect(normalizePreferences({ highContrast: false }).highContrast).toBe("system");
  expect(normalizePreferences({ highContrast: "standard" }).highContrast).toBe("standard");
  expect(normalizePreferences({ highContrast: "high" }).highContrast).toBe("high");
  expect(normalizePreferences({ highContrast: "more" }).highContrast).toBe("system");
});

test("high contrast is in effect when chosen, or when the device asks and the reader left it to the device", () => {
  expect(contrastIsHigh("high", false)).toBe(true);
  expect(contrastIsHigh("high", true)).toBe(true);
  expect(contrastIsHigh("system", true)).toBe(true);
  expect(contrastIsHigh("system", false)).toBe(false);
  expect(contrastIsHigh("standard", true)).toBe(false);
  expect(contrastIsHigh("standard", false)).toBe(false);
});

test("the boot script writes false for standard, true for high and nothing for the device", () => {
  expect(bootAttributes({ highContrast: "standard" })["data-high-contrast"]).toBe("false");
  expect(bootAttributes({ highContrast: "high" })["data-high-contrast"]).toBe("true");
  expect(bootAttributes({ highContrast: true })["data-high-contrast"]).toBe("true");
  expect(bootAttributes({ highContrast: "system" })).not.toHaveProperty("data-high-contrast");
  expect(bootAttributes({ highContrast: false })).not.toHaveProperty("data-high-contrast");
  expect(bootAttributes({ theme: "dark" })["data-theme"]).toBe("dark");
});

test("applying the preferences writes the same contrast attribute as the boot script", () => {
  const light = { ...DEFAULT_PREFERENCES, theme: "light" as const };
  expect(appliedAttributes({ ...light, highContrast: "standard" })).toEqual({ "data-theme": "light", "data-high-contrast": "false" });
  expect(appliedAttributes({ ...light, highContrast: "high" })).toEqual({ "data-theme": "light", "data-high-contrast": "true" });
  expect(appliedAttributes({ ...light, highContrast: "system", largerText: true })).toEqual({ "data-theme": "light", "data-larger-text": "true" });
});

test("Settings says which theme, contrast, text size and motion are in effect", () => {
  expect(themeLine("system", "dark")).toBe("Dark now, because your device is set to dark.");
  expect(themeLine("light", "light")).toBe("Light on every device, whatever the device is set to.");
  expect(contrastLine("system", true)).toBe("High now, because your device asks for more contrast.");
  expect(contrastLine("system", false)).toBe("Standard now. High contrast comes on when your device asks for more.");
  expect(contrastLine("standard", true)).toBe("Standard, although your device asks for more contrast.");
  expect(contrastLine("high", false)).toBe("High: darker text, stronger edges and a thicker focus ring, on every device.");
  expect(textLine(true)).toBe("Larger: every size is an eighth bigger, at every width.");
  expect(motionLine(false, true)).toBe("Reduced now, because your device asks for less motion.");
  expect(motionLine(true, false)).toBe("Reduced: every animation shows its end state at once.");
});

test("Settings opens the tab in the address, and Security when a sign-in confirmation comes back", () => {
  expect(settingsTab(null)).toBe("profile");
  expect(settingsTab("preferences")).toBe("preferences");
  expect(settingsTab("keys")).toBe("profile");
  expect(settingsHref("/settings", "profile")).toBe("/settings");
  expect(settingsHref("/settings", "security")).toBe("/settings?tab=security");
  expect(returnsFromConfirmation(`#oidc=${encodeURIComponent("code=abc&state=pw.s1")}`)).toBe(true);
  expect(returnsFromConfirmation(`#oidc=${encodeURIComponent("code=abc&state=web.s1")}`)).toBe(false);
  expect(returnsFromConfirmation("")).toBe(false);
});

test("the account facts leave out what the account does not record and name the way it signs in", () => {
  expect(accountFacts(READER).map((fact) => fact.label)).toEqual(["Email"]);
  expect(signInFacts({ ...READER, authProvider: "LOCAL", hasPassword: true, twoFactorEnabled: false })).toEqual([
    { label: "Signs in with", value: "Email and password" },
    { label: "Password", value: "Set" },
    { label: "Two-step verification", value: "Off" }
  ]);
  expect(signInFacts({ ...READER, authProvider: "google", hasPassword: false })[0]).toEqual({ label: "Signs in with", value: "Google" });
});

test("a managed key shows only its last characters, and only a saved or unreadable value can be cleared", () => {
  expect(maskedValue({ configured: true, hint: "x9Qa" })).toBe("••••••••x9Qa");
  expect(maskedValue({ configured: false, hint: null })).toBe("Not set");
  expect(hasStoredOverride({ source: "database" })).toBe(true);
  expect(hasStoredOverride({ source: "environment", overrideUnreadable: true })).toBe(true);
  expect(hasStoredOverride({ source: "environment" })).toBe(false);
});

test("a status in a table carries an icon and words, and pages count what they list", () => {
  const status = html(createElement(StatusBadge, { tone: "error", label: "Suspended", note: "since 18 Nov 2026" }));
  expect(status).toContain("lucide-octagon-alert");
  expect(words(status)).toBe("Suspended since 18 Nov 2026");
  const pages = html(createElement(Pagination, { page: 2, pages: 3, total: 41, onPage: () => undefined, noun: { one: "account", many: "accounts" } }));
  expect(words(pages)).toBe("Page 2 of 3 · 41 accounts Previous Next");
});
