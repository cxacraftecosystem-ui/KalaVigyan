from __future__ import annotations

from typing import Any

__all__ = ["tailwind_ts"]

FLAT_COLOURS = ("ground", "raised", "sunk", "rule", "rule-strong", "terracotta")
COLOUR_GROUPS = {
    "ink": {"1": "ink-1", "2": "ink-2", "3": "ink-3"},
    "indigo": {"DEFAULT": "indigo", "hover": "indigo-hover", "wash": "indigo-wash", "on": "on-indigo"},
    "madder": {"DEFAULT": "madder", "wash": "madder-wash", "on": "on-madder"},
    "turmeric": {"DEFAULT": "turmeric", "wash": "turmeric-wash", "text": "turmeric-text"},
    "error": {"DEFAULT": "error", "wash": "error-wash"},
    "warning": {"DEFAULT": "warning", "wash": "warning-wash"},
    "info": {"DEFAULT": "info", "wash": "info-wash"},
    "success": {"DEFAULT": "success", "wash": "success-wash"},
}
HEAD = (
    'import type { Config } from "tailwindcss";',
    "",
    "const c = (name: string) => `rgb(var(--c-${name}) / <alpha-value>)`;",
    "",
    "const config: Config = {",
    '  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],',
    '  darkMode: ["class", \'[data-theme="dark"]\'],',
    "  theme: {",
    '    screens: { sm: "640px", md: "768px", lg: "1024px", rail: "1200px", xl: "1280px", "2xl": "1536px" },',
    "    colors: {",
    '      transparent: "transparent", current: "currentColor", inherit: "inherit",',
)
COLOUR_TAIL = (
    '      white: "rgb(255 255 255 / <alpha-value>)"',
    "    },",
    "    fontFamily: {",
    '      headline: ["var(--font-headline)"], reading: ["var(--font-reading)"], serif: ["var(--font-reading)"],',
    '      ui: ["var(--font-ui)"], sans: ["var(--font-ui)"], code: ["var(--font-code)"]',
    "    },",
    "    fontSize: {",
)
TAIL = (
    "    },",
    '    fontWeight: { light: "300", normal: "400", medium: "500", semibold: "600" },',
    '    borderRadius: { none: "0", plate: "2px", control: "4px", card: "6px", sheet: "14px", pill: "9999px", full: "9999px" },',
    '    boxShadow: { none: "none", pop: "var(--shadow-pop)", label: "var(--shadow-label)", sheet: "var(--shadow-sheet)" },',
    "    backdropBlur: {},",
    '    transitionDuration: { press: "var(--dur-press)", state: "var(--dur-state)", panel: "var(--dur-panel)", dip: "var(--dur-dip)", oxidise: "var(--dur-oxidise)" },',
    '    transitionTimingFunction: { out: "var(--ease-out)", "in-out": "var(--ease-inout)", linear: "linear", toggle: "var(--ease-toggle)" },',
    "    extend: {",
    '      spacing: { section: "var(--space-section)", control: "var(--control-h)", "control-sm": "var(--control-h-sm)", input: "var(--input-h)", target: "var(--target)" },',
    '      maxWidth: { measure: "var(--measure)", content: "var(--content-max)" },',
    '      zIndex: { sticky: "20", appbar: "30", popover: "70", scrim: "80", sheet: "85", dialog: "90", toast: "110", skip: "120" }',
    "    }",
    "  },",
    "  plugins: []",
    "};",
    "",
    "export default config;",
)


def _key(name: str) -> str:
    return name if name.isidentifier() else f'"{name}"'


def _group_line(group: str, members: dict[str, str]) -> str:
    named = ", ".join(f'{_key(key)}: c("{token}")' for key, token in members.items())
    return f"      {group}: {{ {named} }},"


def _size_line(name: str, size: dict[str, Any]) -> str:
    return (
        f'      {_key(name)}: ["var(--text-{name})", {{ lineHeight: "var(--lh-{name})", '
        f'letterSpacing: "var(--track-{name})", fontWeight: "{size["weight"]}" }}],'
    )


def tailwind_ts(tokens: dict[str, Any]) -> str:
    lines = [*HEAD, "      " + ", ".join(f'"{name}": c("{name}")' for name in FLAT_COLOURS) + ","]
    lines += [_group_line(group, members) for group, members in COLOUR_GROUPS.items()]
    lines += [
        *COLOUR_TAIL,
        *(_size_line(name, size) for name, size in tokens["type"]["scale"].items()),
        *TAIL,
    ]
    return "\n".join(lines) + "\n"
