"use client";

import { useCallback, useSyncExternalStore } from "react";

function matchesNow(query: string): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia(query).matches;
}

function matchesOnServer(): boolean {
  return false;
}

export function useDeviceMatches(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      if (typeof window.matchMedia !== "function") return () => undefined;
      const media = window.matchMedia(query);
      media.addEventListener("change", onChange);
      return () => media.removeEventListener("change", onChange);
    },
    [query]
  );
  const snapshot = useCallback(() => matchesNow(query), [query]);
  return useSyncExternalStore(subscribe, snapshot, matchesOnServer);
}
