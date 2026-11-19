"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { returnsFromConfirmation, settingsHref, settingsTab, type SettingsTab } from "@/components/settings/settingsTabs";

export function useSettingsTab(): [SettingsTab, (next: string) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const query = useSearchParams().get("tab");
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (returnsFromConfirmation(window.location.hash)) setConfirming(true);
  }, []);

  const choose = useCallback(
    (next: string) => {
      setConfirming(false);
      router.replace(settingsHref(pathname, settingsTab(next)), { scroll: false });
    },
    [pathname, router]
  );

  return [confirming ? "security" : settingsTab(query), choose];
}