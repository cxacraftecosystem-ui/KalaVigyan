import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { craftOfSubjects } from "@/components/monograph/kinds/data/CitationToolView";
import { DrawingView } from "@/components/monograph/kinds/general/DrawingView";
import { SpecPicture } from "@/components/monograph/kinds/plates/SpecPicture";
import { drawingRoles, resolvedDrawing, THEME_VARIANTS } from "@/lib/componentSpecsGeneral";
import type { MonographComponent } from "@/lib/monographDocument";

const COMPONENT = { label: "bastar-dhokra/process/core", kind: "drawing", subjects: ["craft:Bastar-Dhokra"] } as unknown as MonographComponent;
const ROLES = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 200"><rect width="9" height="9" fill="var(--ink-1)"/></svg>';
const PAINTED = (hex: string) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 200"><rect width="9" height="9" fill="${hex}"/></svg>`;
const THEMES = { light: PAINTED("#1C1815"), dark: PAINTED("#ECEAE3"), hcLight: PAINTED("#000000"), hcDark: PAINTED("#FFFFFF") };
const HEAD = { title: "u0001", caption: null };
const TOKENS_CSS = readFileSync(join(__dirname, "..", "app", "tokens.css"), "utf8");
const THEMES_CSS = readFileSync(join(__dirname, "..", "components", "monograph", "kinds", "general", "themes.css"), "utf8");
const ROOT_RULE = /^\s*(:root[^{]*?)\s*\{/gm;
const MEDIA_RULE = /^@media ([^{]+?)\s*\{/gm;

function drawn(spec: Record<string, unknown>): string {
  return renderToStaticMarkup(createElement(DrawingView, { component: COMPONENT, spec, unitRefs: [], renderUnit: (ref: string) => `[${ref}]`, renderComponent: () => null }));
}

function themeSelectors(css: string): { roots: string[]; media: string[] } {
  const before = css.split(/\.tscope-|\.kv-themed/)[0];
  return { roots: [...before.matchAll(ROOT_RULE)].map((found) => found[1]).filter((rule) => !rule.includes("larger-text")), media: [...before.matchAll(MEDIA_RULE)].map((found) => found[1]) };
}

test("a drawing served in four themes draws one image per theme for the page to choose by its own theme", () => {
  const html = drawn({ head: HEAD, svg: ROLES, alt: "u0002", themes: THEMES });
  const variants = [...html.matchAll(/data-theme-variant="([^"]+)"/g)].map((found) => found[1]);
  expect(variants).toEqual([...THEME_VARIANTS]);
  expect(html).toContain(encodeURIComponent("#ECEAE3"));
  expect(html).toContain('data-drawing="themed"');
  expect(html).not.toContain("kv-general-sheet");
});

test("a drawing in roles without its themes waits for the page's tokens, and a fixed one keeps its specimen mat", () => {
  expect(drawingRoles(ROLES)).toBe(true);
  expect(resolvedDrawing(ROLES, (role) => (role === "ink-1" ? " rgb(28 24 21)" : ""))).toContain('fill="rgb(28 24 21)"');
  expect(resolvedDrawing(ROLES, () => "")).toBe(ROLES);
  const waiting = drawn({ head: HEAD, svg: ROLES, alt: "u0002" });
  expect(waiting).toContain('data-drawing="roles"');
  expect(waiting).not.toContain("<img");
  const fixed = drawn({ head: HEAD, svg: PAINTED("#1C1815"), alt: "u0002" });
  expect(fixed).toContain("kv-general-sheet");
});

test("a contributed drawing given as a picture is drawn once per theme from the server's themed address", () => {
  const picture = { src: "/api/crafts/contributed/0c8e2a4e-1d2b-4c3d-8e9f-0a1b2c3d4e5f", width: 640, height: 480, alt: "The core in its clay", loading: null, fetchPriority: null, decoding: null, themed: true };
  const html = renderToStaticMarkup(createElement(SpecPicture, { picture }));
  expect([...html.matchAll(/src="([^"]+)"/g)].map((found) => found[1].split("?theme=")[1])).toEqual([...THEME_VARIANTS]);
  expect(html.match(/alt="The core in its clay"/g)).toHaveLength(4);
  const plain = renderToStaticMarkup(createElement(SpecPicture, { picture: { ...picture, themed: undefined } }));
  expect(plain.match(/<img/g)).toHaveLength(1);
});

test("the variants follow the same theme selectors as the generated tokens", () => {
  const tokens = themeSelectors(TOKENS_CSS);
  const themes = themeSelectors(THEMES_CSS);
  expect(themes.roots).toEqual(tokens.roots);
  expect(themes.media).toEqual(tokens.media);
});

test("Cite this monograph finds its craft among the component's subjects", () => {
  expect(craftOfSubjects(["category:textiles", "craft:Kutch-Ajrakh"])).toBe("Kutch-Ajrakh");
  expect(craftOfSubjects(["category:textiles"])).toBeNull();
});
