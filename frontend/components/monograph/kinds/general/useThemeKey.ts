"use client";

import { useSyncExternalStore } from "react";

const THEME_QUERIES = ["(prefers-color-scheme: dark)", "(prefers-contrast: more)"] as const;
const THEME_ATTRIBUTES = ["data-theme", "data-high-contrast"];

function subscribe(changed: () => void): () => void {
  const observer = new MutationObserver(changed);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: THEME_ATTRIBUTES });
  const queries = THEME_QUERIES.map((query) => window.matchMedia(query));
  queries.forEach((query) => query.addEventListener("change", changed));
  return () => {
    observer.disconnect();
    queries.forEach((query) => query.removeEventListener("change", changed));
  };
}

function themeKey(): string {
  const root = document.documentElement;
  const media = THEME_QUERIES.map((query) => (window.matchMedia(query).matches ? "1" : "0"));
  return [root.getAttribute("data-theme") ?? "", root.getAttribute("data-high-contrast") ?? "", ...media].join("|");
}

export function useThemeKey(): string | null {
  return useSyncExternalStore(subscribe, themeKey, () => null);
}

export function tokenValue(role: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(`--${role}`);
}
