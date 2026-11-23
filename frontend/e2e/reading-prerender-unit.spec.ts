import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { craftFieldVoices, FIELD_VOICES_UNAVAILABLE } from "@/app/(reading)/crafts/[slug]/craftFieldVoices";
import type { MonographDocument } from "@/lib/monographDocument";
import { PAGE_LANGUAGES_UNAVAILABLE, serverPageLanguages } from "@/lib/monographLanguagesServer";
import { documentOrAbsent, DOCUMENT_UNAVAILABLE, shellParams } from "@/lib/monographRenderServer";
import { documentDigest } from "@/lib/monographRenderShell";
import { PRERENDERED_PAGES, prerenderedParams } from "@/lib/server/readingPages";
import type { StaticPages } from "@/lib/sitePagesContract";

const ROUTES = join(__dirname, "..", "app", "(reading)");
const route = (...parts: string[]) => readFileSync(join(ROUTES, ...parts, "page.tsx"), "utf8");
const golden = (): StaticPages => JSON.parse(readFileSync(join(__dirname, "..", "..", "shared", "site.pages.golden.json"), "utf8")) as StaticPages;

test("the build prerenders only the chosen pages the server lists, in the chosen order, and nothing when the list cannot be read", () => {
  expect(prerenderedParams(golden(), "crafts")).toEqual([{ slug: "Kutch-Ajrakh" }]);
  const listed = { ...golden(), crafts: ["Zalakdozi", "Bastar-Dhokra", "Agates-Of-Cambay", "Kutch-Ajrakh"] };
  expect(prerenderedParams(listed, "crafts")).toEqual([{ slug: "Kutch-Ajrakh" }, { slug: "Bastar-Dhokra" }]);
  expect(prerenderedParams(golden(), "categories")).toEqual([]);
  expect(prerenderedParams({ ...golden(), categories: ["Stone-Craft-Category", "Textiles-Based-Craft-Category"] }, "categories")).toEqual([{ slug: "Textiles-Based-Craft-Category" }, { slug: "Stone-Craft-Category" }]);
  expect(prerenderedParams(null, "crafts")).toEqual([]);
});

test("the pages read at build are few and named once, so one slow page elsewhere cannot hold the build", () => {
  for (const kind of ["crafts", "categories"] as const) {
    expect(new Set(PRERENDERED_PAGES[kind]).size).toBe(PRERENDERED_PAGES[kind].length);
    expect(PRERENDERED_PAGES[kind].length).toBeLessThanOrEqual(6);
  }
  expect(PRERENDERED_PAGES.crafts).toContain("Kutch-Ajrakh");
});

test("every reading route with static params takes them from the policy and renders the rest on first request, kept for a week", () => {
  const routes = [route("crafts", "[slug]"), route("crafts", "[slug]", "monograph"), route("categories", "[slug]"), route("categories", "[slug]", "monograph")];
  expect(route("crafts", "[slug]")).toContain('return prerenderedPages("crafts");');
  for (const source of routes.slice(1)) expect(source).toMatch(/return previewStaticParams\("(craft|category)"\);/);
  for (const source of routes) {
    expect(source).toContain("export const dynamicParams = true;");
    expect(source).toContain("export const revalidate = 604800;");
  }
});

test("the rest of each prerendered craft with an authored shell is prerendered at that craft's own version and content", () => {
  const shelled = { subjectSlug: "Kutch-Ajrakh", version: 3, shell: "<section></section>", content: { units: {} }, specs: {}, fragments: {} } as unknown as MonographDocument;
  const plain = { subjectSlug: "Bastar-Dhokra", version: 12, shell: null } as MonographDocument;
  expect(shellParams([shelled, plain, null])).toEqual([{ slug: "Kutch-Ajrakh", version: `v3-${documentDigest(shelled)}` }]);
  expect(documentDigest(shelled)).toMatch(/^[0-9a-f]{8}$/);
  expect(readFileSync(join(ROUTES, "crafts", "[slug]", "shell", "[version]", "route.ts"), "utf8")).toContain("return prerenderedShells();");
});

test("a monograph the server does not hold is absent, and any other failed read fails the render so no wrong page or 404 is kept", () => {
  expect(documentOrAbsent({ ok: true, body: "document" })).toBe("document");
  expect(documentOrAbsent({ ok: false, failure: "refused", status: 404 })).toBeNull();
  expect(() => documentOrAbsent({ ok: false, failure: "timeout", status: null })).toThrow(`${DOCUMENT_UNAVAILABLE}: timeout`);
  expect(() => documentOrAbsent({ ok: false, failure: "failed", status: 503 })).toThrow(DOCUMENT_UNAVAILABLE);
  expect(route("categories", "[slug]")).toContain("requiredCraftCatalogue()");
});

async function withApiAnswering<T>(status: number | "timeout", run: () => Promise<T>): Promise<T> {
  const holder = globalThis as unknown as { fetch: typeof fetch };
  const saved = { fetch: holder.fetch, origin: process.env.API_ORIGIN };
  process.env.API_ORIGIN = "https://api.kalavigyan.example";
  holder.fetch = async () => {
    if (status === "timeout") throw new DOMException("The operation timed out.", "TimeoutError");
    return new Response(JSON.stringify({ detail: "Not available" }), { status, headers: { "content-type": "application/json" } });
  };
  try {
    return await run();
  } finally {
    holder.fetch = saved.fetch;
    if (saved.origin === undefined) delete process.env.API_ORIGIN;
    else process.env.API_ORIGIN = saved.origin;
  }
}

test("a craft's field voices and a page's languages are absent only when the server holds none, and any other failed read fails the render so the last good page is kept", async () => {
  for (const failure of [503, 500, "timeout"] as const) {
    await withApiAnswering(failure, async () => {
      await expect(craftFieldVoices("Kutch-Ajrakh")).rejects.toThrow(FIELD_VOICES_UNAVAILABLE);
      await expect(serverPageLanguages("craft", "Kutch-Ajrakh")).rejects.toThrow(PAGE_LANGUAGES_UNAVAILABLE);
    });
  }
  await withApiAnswering(404, async () => {
    expect(await craftFieldVoices("No-Such-Craft")).toBeNull();
    expect(await serverPageLanguages("category", "No-Such-Category")).toBeNull();
  });
});
