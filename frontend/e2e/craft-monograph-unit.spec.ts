import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { getPathMatch } from "next/dist/shared/lib/router/utils/path-match";

import nextConfig, { APPROVED_MONOGRAPHS } from "../next.config";

const PUBLIC = join(__dirname, "..", "public");
const APPROVED_FILE = "/monographs/kutch-ajrakh/index.html";
const CRAFT_ROUTE = join(__dirname, "..", "app", "(reading)", "crafts", "[slug]", "page.tsx");

function approved(): string {
  return readFileSync(join(PUBLIC, APPROVED_FILE), "utf8");
}

function matches(source: string, path: string): boolean {
  return getPathMatch(source, { strict: true, removeUnnamedParams: true })(path) !== false;
}

test("the Kutch Ajrakh craft page is the React page, with no rewrite to the static file", async () => {
  expect(nextConfig.rewrites).toBeUndefined();
  const route = readFileSync(CRAFT_ROUTE, "utf8");
  expect(route).toContain("<MonographShellPage document={document} deferred languages={languages} />");
  expect(route).toContain("<MonographDocumentPage document={document} deferred languages={languages} />");
  expect(route).not.toContain("MonographHandover");
});

test("the approved page stays beside the app as the parity reference, kept out of search", async () => {
  expect(approved()).toContain("<title>KalaVigyan · Kutch Ajrakh</title>");
  const rules = await nextConfig.headers!();
  const kept = rules.find((rule) => rule.source === APPROVED_MONOGRAPHS);
  expect(kept?.headers).toEqual([{ key: "X-Robots-Tag", value: "noindex" }]);
  expect(matches(APPROVED_MONOGRAPHS, APPROVED_FILE)).toBe(true);
  expect(matches(APPROVED_MONOGRAPHS, "/crafts/Kutch-Ajrakh")).toBe(false);
});

test("every picture of the approved page is served beside it", () => {
  const pictures = [...approved().matchAll(/<img[^>]*\ssrc="([^"]+)"/g)].map((found) => found[1]).filter((src) => !src.startsWith("data:"));
  expect(pictures.length).toBeGreaterThan(0);
  for (const src of pictures) {
    expect(src, src).toMatch(/^\/monographs\/kutch-ajrakh\/img\//);
    expect(existsSync(join(PUBLIC, src)), src).toBe(true);
  }
});

test("each Ask next question of the approved page opens the ask page for Kutch Ajrakh", () => {
  const asks = [...approved().matchAll(/<a href="([^"]+)" data-ask="([^"]+)">/g)];
  expect(asks).toHaveLength(6);
  for (const [, href, question] of asks) {
    const url = new URL(href.replaceAll("&amp;", "&"), "https://reader.test");
    expect(url.pathname).toBe("/ask");
    expect(url.searchParams.get("q")).toBe(question);
    expect(url.searchParams.get("craft")).toBe("Kutch-Ajrakh");
  }
});
