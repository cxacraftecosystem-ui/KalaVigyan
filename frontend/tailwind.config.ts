import type { Config } from "tailwindcss";

import { retiredColors, retiredUtilityColors } from "./tailwind.migration";

const c = (name: string) => `rgb(var(--c-${name}) / <alpha-value>)`;

const legacyInk = { 900: c("ink-1"), 700: c("ink-2"), 500: c("ink-3") };
const legacyColors = {
  line: { 200: c("rule") }, surface: { 50: c("sunk") },
  progress: { track: c("sunk") },
  white: "rgb(255 255 255 / <alpha-value>)"
};
const legacyFontSize = {
  xs: ["var(--text-caption)", { lineHeight: "var(--lh-caption)" }], sm: ["var(--text-ui)", { lineHeight: "var(--lh-ui)" }], base: ["var(--text-ui-lg)", { lineHeight: "var(--lh-ui-lg)" }],
  lg: ["var(--text-body-sm)", { lineHeight: "var(--lh-body-sm)" }]
};
const legacyRadius = { sm: "4px", md: "6px" };

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    screens: { sm: "640px", md: "768px", lg: "1024px", rail: "1200px", xl: "1280px", "2xl": "1536px" },
    colors: {
      transparent: "transparent", current: "currentColor", inherit: "inherit",
      "ground": c("ground"), "raised": c("raised"), "sunk": c("sunk"), "rule": c("rule"), "rule-strong": c("rule-strong"), "terracotta": c("terracotta"),
      ink: { ...legacyInk, "1": c("ink-1"), "2": c("ink-2"), "3": c("ink-3") },
      indigo: { DEFAULT: c("indigo"), hover: c("indigo-hover"), wash: c("indigo-wash"), on: c("on-indigo") },
      madder: { DEFAULT: c("madder"), wash: c("madder-wash"), on: c("on-madder") },
      turmeric: { DEFAULT: c("turmeric"), wash: c("turmeric-wash"), text: c("turmeric-text") },
      error: { 600: c("error"), DEFAULT: c("error"), wash: c("error-wash") },
      warning: { DEFAULT: c("warning"), wash: c("warning-wash") },
      info: { DEFAULT: c("info"), wash: c("info-wash") },
      success: { DEFAULT: c("success"), wash: c("success-wash") },
      primary: c("indigo"), "primary-foreground": c("on-indigo"), ring: c("indigo"), border: c("rule"), input: c("rule-strong"),
      background: c("ground"), foreground: c("ink-1"), card: c("raised"), popover: c("raised"), "popover-foreground": c("ink-1"), muted: c("sunk"), "muted-foreground": c("ink-3"),
      destructive: c("madder"), "destructive-foreground": c("on-madder"),
      ...legacyColors,
      ...retiredColors(c)
    },
    fontFamily: {
      headline: ["var(--font-headline)"], reading: ["var(--font-reading)"], serif: ["var(--font-reading)"],
      ui: ["var(--font-ui)"], sans: ["var(--font-ui)"], display: ["var(--font-ui)"], code: ["var(--font-code)"]
    },
    fontSize: {
      ...legacyFontSize,
      caption: ["var(--text-caption)", { lineHeight: "var(--lh-caption)", letterSpacing: "var(--track-caption)", fontWeight: "400" }],
      label: ["var(--text-label)", { lineHeight: "var(--lh-label)", letterSpacing: "var(--track-label)", fontWeight: "500" }],
      ui: ["var(--text-ui)", { lineHeight: "var(--lh-ui)", letterSpacing: "var(--track-ui)", fontWeight: "500" }],
      "ui-lg": ["var(--text-ui-lg)", { lineHeight: "var(--lh-ui-lg)", letterSpacing: "var(--track-ui-lg)", fontWeight: "400" }],
      h4: ["var(--text-h4)", { lineHeight: "var(--lh-h4)", letterSpacing: "var(--track-h4)", fontWeight: "600" }],
      figcaption: ["var(--text-figcaption)", { lineHeight: "var(--lh-figcaption)", letterSpacing: "var(--track-figcaption)", fontWeight: "400" }],
      quote: ["var(--text-quote)", { lineHeight: "var(--lh-quote)", letterSpacing: "var(--track-quote)", fontWeight: "400" }],
      "body-sm": ["var(--text-body-sm)", { lineHeight: "var(--lh-body-sm)", letterSpacing: "var(--track-body-sm)", fontWeight: "400" }],
      body: ["var(--text-body)", { lineHeight: "var(--lh-body)", letterSpacing: "var(--track-body)", fontWeight: "400" }],
      lede: ["var(--text-lede)", { lineHeight: "var(--lh-lede)", letterSpacing: "var(--track-lede)", fontWeight: "400" }],
      h3: ["var(--text-h3)", { lineHeight: "var(--lh-h3)", letterSpacing: "var(--track-h3)", fontWeight: "500" }],
      h2: ["var(--text-h2)", { lineHeight: "var(--lh-h2)", letterSpacing: "var(--track-h2)", fontWeight: "480" }],
      h1: ["var(--text-h1)", { lineHeight: "var(--lh-h1)", letterSpacing: "var(--track-h1)", fontWeight: "470" }],
      title: ["var(--text-title)", { lineHeight: "var(--lh-title)", letterSpacing: "var(--track-title)", fontWeight: "480" }],
      hero: ["var(--text-hero)", { lineHeight: "var(--lh-hero)", letterSpacing: "var(--track-hero)", fontWeight: "460" }],
      numeral: ["var(--text-numeral)", { lineHeight: "var(--lh-numeral)", letterSpacing: "var(--track-numeral)", fontWeight: "300" }],
      stat: ["var(--text-stat)", { lineHeight: "var(--lh-stat)", letterSpacing: "var(--track-stat)", fontWeight: "480" }]
    },
    fontWeight: { light: "300", normal: "400", medium: "500", semibold: "600", bold: "600" },
    borderRadius: { ...legacyRadius, none: "0", plate: "2px", control: "4px", card: "6px", sheet: "14px", pill: "9999px", full: "9999px" },
    boxShadow: { none: "none", pop: "var(--shadow-pop)", label: "var(--shadow-label)", sheet: "var(--shadow-sheet)" },
    backdropBlur: {},
    transitionDuration: { press: "var(--dur-press)", state: "var(--dur-state)", panel: "var(--dur-panel)", dip: "var(--dur-dip)", oxidise: "var(--dur-oxidise)" },
    transitionTimingFunction: { out: "var(--ease-out)", "in-out": "var(--ease-inout)", linear: "linear", toggle: "var(--ease-toggle)" },
    extend: {
      ...retiredUtilityColors(c),
      spacing: { section: "var(--space-section)", control: "var(--control-h)", "control-sm": "var(--control-h-sm)", input: "var(--input-h)", target: "var(--target)" },
      maxWidth: { measure: "var(--measure)", content: "var(--content-max)" },
      zIndex: { sticky: "20", appbar: "30", popover: "70", scrim: "80", sheet: "85", dialog: "90", toast: "110", skip: "120" }
    }
  },
  plugins: []
};

export default config;
