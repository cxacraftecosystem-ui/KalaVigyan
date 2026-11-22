import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";

import { askPagePath, signedOutAskHref } from "@/lib/askEntry";
import { atlasMetadata, craftPageMetadata, SHARE_PICTURE_WIDTH } from "@/lib/readingMetadata";
import { isReadingRoute, READING_ROUTES } from "@/lib/readingRoutes";
import { mayHoldSession } from "@/lib/session";
import { ENGLISH } from "@/lib/answerLanguages";
import { ANSWER_LANGUAGES_PATH, checkedShareLink, EXPLAINER_SHARE_PATH, LESSON_SHARE_PATH, NOT_SHARED, sharedAddress, shareLinkShape, SHARED_ANSWER_PATH, withReadingLanguages } from "@/lib/shareContract";
import { SHARE_NOTICE } from "@/lib/shareNotice";
import { parseShape, ShapeError } from "@/lib/shape";

import { curatedPage } from "./craftPageFixture";
import { FRONTEND } from "./moduleGraph";

const TOKEN = "Zk3p9QmVt2LxW8rYbN4cHdFsA7gJeKu1oPiTzRq6Smw";
const SIGNED_IN_TOOLS = ["/ask", "/saved", "/lessons", "/settings", "/admin", "/contribute"];
const READING_PAGES = ["crafts/page.tsx", "crafts/[slug]/page.tsx", "map/page.tsx", "compare/page.tsx", "voices/[id]/page.tsx", "shared/answers/[token]/page.tsx", "shared/lessons/[token]/page.tsx"];
const SIGNED_IN_PAGES = ["ask/page.tsx", "saved/page.tsx", "lessons/page.tsx", "settings/page.tsx", "admin/page.tsx", "contribute/page.tsx"];

const source = (file: string) => readFileSync(join(FRONTEND, file), "utf8");

test("the reading routes are everything but asking and the signed-in tools", () => {
  for (const route of READING_ROUTES) {
    expect(isReadingRoute(route)).toBe(true);
    expect(isReadingRoute(`${route}/Kutch-Ajrakh`)).toBe(true);
  }
  expect(SIGNED_IN_TOOLS.filter(isReadingRoute)).toEqual([]);
  expect(isReadingRoute("/craftsmanship")).toBe(false);
});

test("a reading page without a session never probes the signed-in account", () => {
  expect(READING_ROUTES.map((route) => mayHoldSession(`${route}/x`, false))).toEqual(READING_ROUTES.map(() => false));
  expect(mayHoldSession("/ask", false)).toBe(true);
  expect(mayHoldSession("/crafts/Kutch-Ajrakh", true)).toBe(true);
});

test("reading pages live in the (reading) group and the signed-in tools stay in (protected)", () => {
  expect(READING_PAGES.filter((page) => !existsSync(join(FRONTEND, "app", "(reading)", page)))).toEqual([]);
  expect(READING_PAGES.filter((page) => existsSync(join(FRONTEND, "app", "(protected)", page)))).toEqual([]);
  expect(SIGNED_IN_PAGES.filter((page) => !existsSync(join(FRONTEND, "app", "(protected)", page)))).toEqual([]);
});

test("only the signed-in shell sends a reader to sign in; the reading shell never redirects", () => {
  const reading = source("components/shell/ReadingShell.tsx");
  expect(reading).not.toMatch(/router\.(replace|push)|signInHref|redirect\(/);
  expect(source("app/(reading)/layout.tsx")).toContain("ReadingShell");
  expect(source("components/AppShell.tsx")).toMatch(/router\.replace\(signInHref\(/);
});

test("Ask from a reading page carries the craft and the question through sign in", () => {
  expect(askPagePath({ craft: "Kutch-Ajrakh" })).toBe("/ask?craft=Kutch-Ajrakh");
  expect(askPagePath({ craft: "Kutch-Ajrakh", question: "  Why is the cloth soaked in harda?  " })).toBe("/ask?q=Why+is+the+cloth+soaked+in+harda%3F&craft=Kutch-Ajrakh");
  expect(signedOutAskHref({ craft: "Kutch-Ajrakh" })).toBe("/login?next=%2Fask%3Fcraft%3DKutch-Ajrakh");
  expect(askPagePath({})).toBe("/ask");
});

test("a share link has a path and a time exactly while it is shared", () => {
  const shared = { schemaVersion: 1, shared: true, path: SHARED_ANSWER_PATH(TOKEN), sharedAt: "2026-11-18T10:00:00+05:30" };
  expect(checkedShareLink(parseShape(shareLinkShape, shared)).path).toBe(`/shared/answers/${TOKEN}`);
  expect(checkedShareLink(parseShape(shareLinkShape, NOT_SHARED))).toEqual(NOT_SHARED);
  expect(() => checkedShareLink(parseShape(shareLinkShape, { ...shared, path: null }))).toThrow(ShapeError);
  expect(() => parseShape(shareLinkShape, { ...shared, path: "/ask" })).toThrow(ShapeError);
  expect(sharedAddress("https://kalavigyan.vercel.app", parseShape(shareLinkShape, shared))).toBe(`https://kalavigyan.vercel.app/shared/answers/${TOKEN}`);
  expect(sharedAddress("https://kalavigyan.vercel.app", NOT_SHARED)).toBeNull();
  expect([EXPLAINER_SHARE_PATH("e1", 2), LESSON_SHARE_PATH("l1")]).toEqual(["/explainers/e1/versions/2/share", "/lessons/l1/share"]);
});

test("a shared answer reads with the answer languages' script and direction, and in English when they cannot be read", async () => {
  const urdu = { code: "ur", label: "Urdu", autonym: "اردو", script: "Arab", direction: "rtl" as const };
  expect(ANSWER_LANGUAGES_PATH).toBe("/answers/languages");
  expect(await withReadingLanguages(Promise.resolve("answer"), async () => [ENGLISH, urdu])).toEqual({ body: "answer", languages: [ENGLISH, urdu] });
  const quiet = console.error;
  console.error = () => undefined;
  try {
    expect(await withReadingLanguages(Promise.resolve("answer"), async () => Promise.reject(new Error("offline")))).toEqual({ body: "answer", languages: [ENGLISH] });
  } finally {
    console.error = quiet;
  }
  await expect(withReadingLanguages(Promise.reject(new Error("gone")), async () => [ENGLISH])).rejects.toThrow("gone");
  expect(source("components/learn/SharedScreens.tsx")).not.toContain("[ENGLISH]");
});

test("sharing asks first and names what the link makes readable", () => {
  expect(SHARE_NOTICE.answer.body).toBe("Anyone with the link can read your question and this version of the answer with its citations, and download its report as a PDF.");
  expect(SHARE_NOTICE.lesson.body).toBe("Anyone with the link can read this lesson with its citations, and download its slides and handout.");
  expect(new Set(Object.values(SHARE_NOTICE).map((notice) => notice.note))).toEqual(new Set(["Your name, email address and role never appear. Stop sharing and the link stops working."]));
  const control = source("components/learn/ShareControl.tsx");
  expect(control.match(/startSharing\(/g)).toHaveLength(1);
  expect(control).toMatch(/if \(!\(await confirm\(SHARE_NOTICE\[kind\]\)\)\) return;\s+await run\(\(\) => startSharing\(sharePath\)/);
  expect(source("components/learn/ExplainerTools.tsx")).toContain('kind="answer"');
  expect(source("app/(protected)/lessons/[id]/page.tsx")).toContain('kind="lesson"');
});

test("a craft page previews with its name, first lede sentence and masthead plate at a Commons width with its credit", () => {
  const page = curatedPage();
  const metadata = craftPageMetadata(page);
  expect(metadata.title).toBe("Kutch Ajrakh");
  expect(metadata.description).toBe("Kutch Ajrakh is an elaborate resist block-printing technique of direct and resist printing and dyeing, made by Khatri artisans as a double-sided textile.");
  const images = (metadata.openGraph?.images ?? []) as { url: string; width: number; alt: string }[];
  expect(images).toHaveLength(1);
  expect(images[0].url).toBe(`https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Ajrak_Craft.jpeg/${SHARE_PICTURE_WIDTH}px-Ajrak_Craft.jpeg`);
  expect(images[0].alt).toBe("An ajrakh made by Kutch artisans, held up to show its repeated field and multiple borders. Photo: Visdaviva, CC BY-SA 3.0, via Wikimedia Commons");
  expect(craftPageMetadata(curatedPage((body) => (body.masthead.picture = null))).openGraph?.images).toEqual([]);
  expect(craftPageMetadata(curatedPage((body) => (body.lede = []))).description).toBe("Textiles based Craft Category › Hand Block Printing");
  expect(craftPageMetadata(null)).toEqual({});
});

test("the atlas previews with its craft count, and with no count when the catalogue is out of reach", () => {
  expect(atlasMetadata(null).description).toBeUndefined();
  expect(atlasMetadata(null).title).toBe("Crafts");
});
