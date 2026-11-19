"use client";

import { useEffect, type ReactNode } from "react";

import { useThemePreferences } from "@/components/ThemeProvider";
import type { Preferences } from "@/lib/preferences";

export const KIT_PREFERENCES_EVENT = "kv-prefs";
export const READER_ATTRIBUTES = ["data-theme", "data-high-contrast", "data-larger-text", "data-reduced-motion"] as const;

type Flag = "largerText" | "reducedMotion";
type Tool = { key: "theme" | "highContrast" | Flag; label: string; icon: ReactNode };

const TOOLS: readonly Tool[] = [
  {
    key: "theme",
    label: "Dark",
    icon: (
      <>
        <circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeWidth="1.4" />
        <path d="M8 2 A6 6 0 0 1 8 14 Z" fill="currentColor" />
      </>
    )
  },
  {
    key: "highContrast",
    label: "High contrast",
    icon: (
      <>
        <rect x="2" y="2" width="12" height="12" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.4" />
        <path d="M2 14 L14 2 V14 Z" fill="currentColor" />
      </>
    )
  },
  {
    key: "largerText",
    label: "Larger text",
    icon: (
      <>
        <path d="M1.5 13 L5 3.5 L8.5 13 M2.8 10 H7.2" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M10 13 L12.5 7 L15 13 M10.9 11 H14.1" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
      </>
    )
  },
  {
    key: "reducedMotion",
    label: "Reduce motion",
    icon: <path d="M2 8 H12 M8.5 4.5 L12 8 L8.5 11.5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
  }
];

export function toolPatch(key: Tool["key"], pressed: boolean): Partial<Preferences> {
  if (key === "theme") return { theme: pressed ? "light" : "dark" };
  if (key === "highContrast") return { highContrast: pressed ? "standard" : "high" };
  return { [key]: !pressed };
}

export function ReaderTools() {
  const { preferences, resolvedTheme, update } = useThemePreferences();
  const pressed = (key: Tool["key"]) => (key === "theme" ? resolvedTheme === "dark" : key === "highContrast" ? preferences.highContrast === "high" : preferences[key]);
  return (
    <div className="kv-menu-tools" role="group" aria-label="Display">
      {TOOLS.map((tool) => (
        <button key={tool.key} className="kv-tool" type="button" aria-pressed={pressed(tool.key)} onClick={() => update(toolPatch(tool.key, pressed(tool.key)))}>
          <svg viewBox="0 0 16 16" aria-hidden="true">
            {tool.icon}
          </svg>
          <span>{tool.label}</span>
        </button>
      ))}
    </div>
  );
}

export function KitPreferences() {
  useEffect(() => {
    const observer = new MutationObserver(() => window.dispatchEvent(new Event(KIT_PREFERENCES_EVENT)));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: [...READER_ATTRIBUTES] });
    return () => observer.disconnect();
  }, []);
  return null;
}
