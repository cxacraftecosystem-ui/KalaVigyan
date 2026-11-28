"use client";

import { useEffect } from "react";

import { renewSession } from "@/lib/session";

export function useSessionRenewal(signedIn: boolean): void {
  useEffect(() => {
    if (!signedIn) return;
    void renewSession();
    const again = () => {
      if (document.visibilityState === "visible") void renewSession();
    };
    document.addEventListener("visibilitychange", again);
    return () => document.removeEventListener("visibilitychange", again);
  }, [signedIn]);
}
