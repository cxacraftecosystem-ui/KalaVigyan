export type ThemeChoice = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";
export type ContrastChoice = "system" | "standard" | "high";

export type Preferences = {
  theme: ThemeChoice;
  reducedMotion: boolean;
  largerText: boolean;
  highContrast: ContrastChoice;
  answerLanguage: string;
};

export const DEFAULT_PREFERENCES: Preferences = {
  theme: "system",
  reducedMotion: false,
  largerText: false,
  highContrast: "system",
  answerLanguage: "auto"
};

export const PREFERENCES_KEY = "kalavigyan_preferences";
export const PREFERENCES_PATH = "/preferences/me";

export const DARK_MEDIA_QUERY = "(prefers-color-scheme: dark)";
export const MORE_CONTRAST_MEDIA_QUERY = "(prefers-contrast: more)";

export const THEME_COLOR: Record<ResolvedTheme, string> = {
  light: "#F4F5F1",
  dark: "#0E121C"
};

export const THEME_CHOICES: ThemeChoice[] = ["system", "light", "dark"];
export const CONTRAST_CHOICES: ContrastChoice[] = ["system", "standard", "high"];

export const CONTRAST_ATTRIBUTE: Record<ContrastChoice, "true" | "false" | null> = {
  system: null,
  standard: "false",
  high: "true"
};

const ANSWER_LANGUAGE_CHOICE = /^(auto|[a-z]{2,3})$/;

export function contrastChoice(value: unknown): ContrastChoice {
  if (value === true) return "high";
  return CONTRAST_CHOICES.includes(value as ContrastChoice) ? (value as ContrastChoice) : DEFAULT_PREFERENCES.highContrast;
}

export function contrastIsHigh(choice: ContrastChoice, deviceAsksForMore: boolean): boolean {
  return choice === "high" || (choice === "system" && deviceAsksForMore);
}

export function normalizePreferences(value: unknown): Preferences {
  if (!value || typeof value !== "object") return { ...DEFAULT_PREFERENCES };
  const raw = value as Partial<Record<keyof Preferences, unknown>>;
  return {
    theme: THEME_CHOICES.includes(raw.theme as ThemeChoice)
      ? (raw.theme as ThemeChoice)
      : DEFAULT_PREFERENCES.theme,
    reducedMotion: raw.reducedMotion === true,
    largerText: raw.largerText === true,
    highContrast: contrastChoice(raw.highContrast),
    answerLanguage: typeof raw.answerLanguage === "string" && ANSWER_LANGUAGE_CHOICE.test(raw.answerLanguage) ? raw.answerLanguage : DEFAULT_PREFERENCES.answerLanguage
  };
}

export function readStoredPreferences(): Preferences {
  if (typeof window === "undefined") return { ...DEFAULT_PREFERENCES };
  try {
    const raw = window.localStorage.getItem(PREFERENCES_KEY);
    return raw ? normalizePreferences(JSON.parse(raw)) : { ...DEFAULT_PREFERENCES };
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
}

export function writeStoredPreferences(preferences: Preferences): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(PREFERENCES_KEY, JSON.stringify(preferences));
  } catch {
  }
}

export function systemPrefersDark(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  return window.matchMedia(DARK_MEDIA_QUERY).matches;
}

export function resolveTheme(theme: ThemeChoice): ResolvedTheme {
  if (theme === "light" || theme === "dark") return theme;
  return systemPrefersDark() ? "dark" : "light";
}

function setAttribute(root: HTMLElement, attribute: string, value: string | null): void {
  if (value === null) root.removeAttribute(attribute);
  else root.setAttribute(attribute, value);
}

export function applyPreferences(preferences: Preferences): ResolvedTheme {
  const resolved = resolveTheme(preferences.theme);
  if (typeof document === "undefined") return resolved;

  const root = document.documentElement;
  root.setAttribute("data-theme", resolved);
  setAttribute(root, "data-reduced-motion", preferences.reducedMotion ? "true" : null);
  setAttribute(root, "data-larger-text", preferences.largerText ? "true" : null);
  setAttribute(root, "data-high-contrast", CONTRAST_ATTRIBUTE[preferences.highContrast]);

  document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
    meta.removeAttribute("media");
    meta.setAttribute("content", THEME_COLOR[resolved]);
  });
  return resolved;
}

export const PREFERENCES_BOOT_SCRIPT = `(function(){try{` +
  `var d=document.documentElement;` +
  `var p=JSON.parse(window.localStorage.getItem(${JSON.stringify(PREFERENCES_KEY)})||"{}")||{};` +
  `var t=p.theme;` +
  `var c=p.highContrast;` +
  `var dark=t==="dark"||(t!=="light"&&window.matchMedia(${JSON.stringify(DARK_MEDIA_QUERY)}).matches);` +
  `d.setAttribute("data-theme",dark?"dark":"light");` +
  `if(p.reducedMotion===true)d.setAttribute("data-reduced-motion","true");` +
  `if(p.largerText===true)d.setAttribute("data-larger-text","true");` +
  `if(c==="high"||c===true)d.setAttribute("data-high-contrast","true");` +
  `else if(c==="standard")d.setAttribute("data-high-contrast","false");` +
  `}catch(e){}})();`;
