import { CONFIRM_STATE_PREFIX, parseCallbackFragment } from "@/lib/oidcSignIn";

export const SETTINGS_TABS = ["profile", "preferences", "security"] as const;
export type SettingsTab = (typeof SETTINGS_TABS)[number];

export const SETTINGS_TAB_LABELS: Record<SettingsTab, string> = { profile: "Profile", preferences: "Preferences", security: "Security" };

export function settingsTab(query: string | null): SettingsTab {
  return SETTINGS_TABS.find((tab) => tab === query) ?? "profile";
}

export function returnsFromConfirmation(hash: string): boolean {
  return parseCallbackFragment(hash)?.state.startsWith(CONFIRM_STATE_PREFIX) ?? false;
}

export function settingsHref(pathname: string, tab: SettingsTab): string {
  return tab === "profile" ? pathname : `${pathname}?tab=${tab}`;
}