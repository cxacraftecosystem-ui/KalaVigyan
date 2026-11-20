import { expect, test } from "@playwright/test";

import { KEY_PAGES, auditPaths, expectedStatus, pageProblems, returnsTo, type KeyPage, type PageSeen } from "./keyPages";

const DOCUMENT_PAGE: KeyPage = { name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh", marker: { kind: "document", heading: /Ajrakh/ }, audit: true };
const MISSING_PAGE: KeyPage = { name: "Missing", path: "/no-such-page-e2e", marker: { kind: "not-found" }, audit: false };
const ASK_PAGE: KeyPage = { name: "Ask", path: "/ask", marker: { kind: "shell" }, audit: true };
const LOGIN_PAGE: KeyPage = { name: "Sign in", path: "/login", marker: { kind: "sign-in" }, audit: true };

function seen(overrides: Partial<PageSeen> = {}): PageSeen {
  return {
    status: 200,
    finalPath: "/crafts/Kutch-Ajrakh",
    drawn: true,
    heading: "Kutch Ajrakh",
    errorPanels: [],
    shape: { heading: "Kutch Ajrakh", chapters: 9, citations: 120 },
    signInFields: false,
    crashes: [],
    ...overrides
  };
}

test("the key pages are about twenty, each named and reached once", () => {
  expect(KEY_PAGES.length).toBeGreaterThanOrEqual(18);
  expect(new Set(KEY_PAGES.map((page) => page.name)).size).toBe(KEY_PAGES.length);
  expect(new Set(KEY_PAGES.map((page) => page.path)).size).toBe(KEY_PAGES.length);
});

test("the key pages cover the landing, atlas, Kutch Ajrakh, three more curated crafts, a record, a family, a hub, the map, sign-in and the answer page", () => {
  const paths = KEY_PAGES.map((page) => page.path);
  for (const path of ["/", "/crafts", "/crafts/Kutch-Ajrakh", "/crafts/Kasuti-Embroidery", "/crafts/Cane-Bamboo-Craft", "/categories/Textiles-Based-Craft-Category", "/map", "/login", "/ask"]) {
    expect(paths).toContain(path);
  }
  const documents = KEY_PAGES.filter((page) => page.marker.kind === "document" && page.path !== "/crafts/Kutch-Ajrakh" && page.path !== "/crafts/Cane-Bamboo-Craft");
  expect(documents.length).toBeGreaterThanOrEqual(3);
});

test("a page that should not exist must answer 404 and every other page 200", () => {
  expect(expectedStatus({ kind: "not-found" })).toBe(404);
  expect(expectedStatus({ kind: "document", heading: /x/ })).toBe(200);
  expect(expectedStatus({ kind: "shell" })).toBe(200);
});

test("a monograph that answers 200 and draws its chapters and citations passes", () => {
  expect(pageProblems(DOCUMENT_PAGE, seen())).toEqual([]);
});

test("a server error, a crash and an error panel are each named", () => {
  const problems = pageProblems(DOCUMENT_PAGE, seen({ status: 500, crashes: ["TypeError: x is undefined"], errorPanels: ["error-server"] }));
  expect(problems).toEqual(["the page answered 500; it should answer 200", "the page threw: TypeError: x is undefined", "the page shows the error-server panel"]);
});

test("a monograph with the wrong heading, no chapters and no citations fails on each", () => {
  const problems = pageProblems(DOCUMENT_PAGE, seen({ shape: { heading: "Bagru", chapters: 0, citations: 0 } }));
  expect(problems).toEqual(['the monograph is headed "Bagru"; it should match /Ajrakh/', "the monograph draws no chapter", "the monograph draws no citation"]);
});

test("a craft page that draws no monograph at all says so", () => {
  expect(pageProblems(DOCUMENT_PAGE, seen({ shape: null }))).toEqual(["the page draws no monograph"]);
});

test("a page that should be missing passes only on 404 with the page-not-found panel", () => {
  expect(pageProblems(MISSING_PAGE, seen({ status: 404, errorPanels: ["error-not-found"], shape: null }))).toEqual([]);
  expect(pageProblems(MISSING_PAGE, seen({ status: 200, errorPanels: [], shape: null }))).toEqual(["the page answered 200; it should answer 404", "the page does not show the page-not-found panel"]);
});

test("a page that drew nothing within the wait or answered nothing is named", () => {
  expect(pageProblems(LOGIN_PAGE, seen({ status: null, drawn: false, signInFields: true }))).toEqual(["the page answered nothing", "the page drew nothing within the wait"]);
  expect(pageProblems(LOGIN_PAGE, seen({ signInFields: false }))).toEqual(["the sign-in form draws no Email and Password fields"]);
});

test("a signed-in screen passes when it is drawn or when sign-in will return to it", () => {
  expect(returnsTo("/ask", "/ask")).toBe(true);
  expect(returnsTo("/login?next=%2Fask", "/ask")).toBe(true);
  expect(returnsTo("/login?next=%2Fask%3Fcraft%3DKutch-Ajrakh", "/ask")).toBe(true);
  expect(returnsTo("/login", "/ask")).toBe(false);
  expect(returnsTo("/", "/ask")).toBe(false);
  expect(pageProblems(ASK_PAGE, seen({ finalPath: "/" }))).toEqual(["a signed-out reader ends at /, neither /ask nor sign-in on the way back to it"]);
});

test("the audited pages are the ones asked for, else the reader pages marked for audit", () => {
  expect(auditPaths(" /crafts, ,/map ")).toEqual(["/crafts", "/map"]);
  expect(auditPaths("")).toEqual([
    "/",
    "/crafts",
    "/crafts/Kutch-Ajrakh",
    "/crafts/Bastar-Dhokra",
    "/crafts/Kasuti-Embroidery",
    "/categories/Textiles-Based-Craft-Category",
    "/map",
    "/login",
    "/ask"
  ]);
});
