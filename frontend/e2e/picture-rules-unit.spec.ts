import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { getPathMatch } from "next/dist/shared/lib/router/utils/path-match";

import nextConfig, { APPROVED_MONOGRAPHS, CONTENT_SECURITY_POLICY, MEDIA_BUCKET_ORIGIN, WEB_PICTURE_SOURCE } from "../next.config";

const COMPONENTS = join(__dirname, "..", "components");

function componentFiles(folder: string): string[] {
  return readdirSync(folder, { withFileTypes: true }).flatMap((entry) => {
    const path = join(folder, entry.name);
    if (entry.isDirectory()) return componentFiles(path);
    return entry.name.endsWith(".tsx") ? [path] : [];
  });
}

function imageSources(policy: string | undefined): string[] {
  return policy?.split("; ").find((entry) => entry.startsWith("img-src "))?.split(" ").slice(1) ?? [];
}

async function policyFor(path: string): Promise<string | undefined> {
  const rules = await nextConfig.headers!();
  const matching = rules.filter((rule) => getPathMatch(rule.source)(path) !== false);
  return matching.flatMap((rule) => rule.headers.filter((header) => header.key === "Content-Security-Policy").map((header) => header.value)).at(-1);
}

test("every page lets pictures load from https sites, so a move to the ask page inside the app shows them, and no page allows plain http or any scheme", async () => {
  expect(WEB_PICTURE_SOURCE).toBe("https:");
  expect(imageSources(CONTENT_SECURITY_POLICY)).toEqual(["'self'", "data:", MEDIA_BUCKET_ORIGIN, WEB_PICTURE_SOURCE]);
  expect(CONTENT_SECURITY_POLICY).not.toMatch(/img-src[^;]*(\*|http:)/);
  for (const path of ["/", "/ask", "/settings", "/crafts/Kutch-Ajrakh", "/map", "/monographs/kutch-ajrakh/index.html"]) expect(await policyFor(path), path).toBe(CONTENT_SECURITY_POLICY);
  const rules = await nextConfig.headers!();
  expect(rules.map((rule) => rule.source)).toEqual(["/:path*", APPROVED_MONOGRAPHS]);
});

test("every component that draws a picture from the web sends no referrer to its site", () => {
  const drawing = componentFiles(COMPONENTS).filter((file) => /\.imageUrl\b/.test(readFileSync(file, "utf8")));
  for (const file of drawing) {
    const text = readFileSync(file, "utf8");
    const starts = [...text.matchAll(/<(img|Image)\b/g)].map((found) => found.index ?? 0);
    expect(starts.length, file).toBeGreaterThan(0);
    for (const start of starts) expect(text.slice(start, text.indexOf("/>", start)), file).toContain('referrerPolicy="no-referrer"');
  }
});
