import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { afterLoad, laterWhenIdle, whenIdle } from "../components/monograph/useShellTrigger";
import { documentPart, documentPartPath, DocumentPartError, joinedDocument, LATEST_READ, laterRead, type DocumentPart } from "../lib/monographDocumentParts";

const part = (at: number, parts: number, body: Record<string, unknown>, version = 4, tag: string | null = null): DocumentPart => ({ schemaVersion: 1, version, part: at, parts, tag, body });
const HINDI_TAG = "v4-abc-hi-0123456789abcdef";
const SHELL_ROUTE = join(__dirname, "..", "app", "(reading)", "crafts", "[slug]", "shell", "[version]", "route.ts");

test("a part is read by its number at the version the first part named", () => {
  expect(documentPartPath("/crafts/Kutch-Ajrakh/monograph", 0, LATEST_READ)).toBe("/crafts/Kutch-Ajrakh/monograph?part=0");
  expect(documentPartPath("/crafts/Kutch-Ajrakh/monograph", 2, { ...LATEST_READ, version: 7 })).toBe("/crafts/Kutch-Ajrakh/monograph?version=7&part=2");
});

test("a translated document's later parts are read in its language at the tag its first part named", () => {
  expect(documentPartPath("/crafts/Kutch-Ajrakh/monograph", 0, { ...LATEST_READ, language: "hi" })).toBe("/crafts/Kutch-Ajrakh/monograph?lang=hi&part=0");
  const first = documentPart({ schemaVersion: 1, version: 4, part: 0, parts: 2, tag: HINDI_TAG, body: { language: "hi" } });
  expect(first.tag).toBe(HINDI_TAG);
  expect(documentPartPath("/crafts/Kutch-Ajrakh/monograph", 1, laterRead(first, "hi"))).toBe(`/crafts/Kutch-Ajrakh/monograph?lang=hi&version=4&tag=${HINDI_TAG}&part=1`);
  expect(() => documentPart({ schemaVersion: 1, version: 4, part: 0, parts: 2, tag: 7, body: {} })).toThrow(DocumentPartError);
});

test("a server that sends the whole document is read as its only part", () => {
  const whole = { schemaVersion: 1, subjectSlug: "Kutch-Ajrakh", version: 3, specs: { a: { x: 1 } }, fragments: {}, shell: null };
  expect(documentPart(whole)).toEqual({ schemaVersion: 1, version: 3, part: 0, parts: 1, tag: null, body: whole });
  expect(joinedDocument([documentPart(whole)])).toEqual(whole);
  expect(documentPart({ schemaVersion: 1, version: 3, part: 1, parts: 3, body: { specs: {} } })).toEqual(part(1, 3, { specs: {} }, 3));
  expect(() => documentPart({ schemaVersion: 1, version: 3, part: 3, parts: 3, body: {} })).toThrow(DocumentPartError);
  expect(() => documentPart([1, 2])).toThrow(DocumentPartError);
});

test("the parts join back into the whole document, its shell and specs in their order", () => {
  const joined = joinedDocument([
    part(0, 3, { title: "Kutch Ajrakh", content: { units: {} } }),
    part(1, 3, { shell: "<section></section>", specs: { first: { t: "a" } }, fragments: {} }),
    part(2, 3, { specs: { second: { t: "b" } }, fragments: { frag: "<p></p>" } })
  ]);
  expect(joined).toEqual({ title: "Kutch Ajrakh", content: { units: {} }, shell: "<section></section>", specs: { first: { t: "a" }, second: { t: "b" } }, fragments: { frag: "<p></p>" } });
  expect(Object.keys(joined.specs as object)).toEqual(["first", "second"]);
});

test("parts read from two readings, or too few of them, refuse to join", () => {
  expect(() => joinedDocument([part(0, 2, {}), part(1, 2, { specs: {} }, 5)])).toThrow("from another reading");
  expect(() => joinedDocument([part(0, 2, { language: "hi" }, 4, HINDI_TAG), part(1, 2, { shell: "<section></section>" }, 4, "v4-abc")])).toThrow("from another reading");
  expect(joinedDocument([part(0, 2, { language: "hi" }, 4, HINDI_TAG), part(1, 2, { shell: "<section></section>" }, 4, HINDI_TAG)]).shell).toBe("<section></section>");
  expect(() => joinedDocument([part(0, 3, {}), part(1, 3, { specs: {} })])).toThrow("has 3 parts, not 2");
  expect(() => joinedDocument([part(1, 2, {})])).toThrow("from its first part");
});

test("the rest of a page starts a while after load, once the browser is idle", () => {
  const calls: string[] = [];
  const timers: (() => void)[] = [];
  const setTimeout = (run: () => void, wait: number) => {
    calls.push(`wait ${wait}`);
    timers.push(run);
    return 3;
  };
  const requestIdleCallback = (run: () => void, options: { timeout: number }) => {
    calls.push(`idle ${options.timeout}`);
    run();
    return 1;
  };
  const view = { setTimeout, clearTimeout: () => calls.push("cleared"), requestIdleCallback, cancelIdleCallback: () => calls.push("cancelled") };
  const stop = laterWhenIdle(view as unknown as Window, () => calls.push("started"));
  expect(calls).toEqual(["wait 5000"]);
  timers.forEach((run) => run());
  stop();
  expect(calls).toEqual(["wait 5000", "idle 2000", "started", "cleared", "cancelled"]);
  const plain: string[] = [];
  const runAtOnce = (run: () => void) => {
    run();
    return 4;
  };
  const noIdle = { setTimeout: runAtOnce, clearTimeout: () => plain.push("cleared") };
  laterWhenIdle(noIdle as unknown as Window, () => plain.push("started"))();
  expect(plain).toEqual(["started", "cleared"]);
  expect(whenIdle({} as Window, () => plain.push("never"))).toBeInstanceOf(Function);
  expect(plain).not.toContain("never");
});

test("a page still loading waits for its load event, and a loaded one goes on at once", () => {
  const heard: string[] = [];
  const view = { addEventListener: (name: string) => heard.push(`listen ${name}`), removeEventListener: (name: string) => heard.push(`stop ${name}`) };
  const loading = afterLoad(view as unknown as Window, { readyState: "interactive" } as Document, () => heard.push("loaded"));
  loading();
  expect(heard).toEqual(["listen load", "stop load"]);
  afterLoad(view as unknown as Window, { readyState: "complete" } as Document, () => heard.push("loaded"));
  expect(heard.at(-1)).toBe("loaded");
});

test("the rest of an authored page is read from the document the page drew when its address still names it", () => {
  const route = readFileSync(SHELL_ROUTE, "utf8");
  expect(route).toContain("documentDigest(current) === address.digest");
  expect(route).toContain("serverCraftDocument(slug, address.version)");
});
