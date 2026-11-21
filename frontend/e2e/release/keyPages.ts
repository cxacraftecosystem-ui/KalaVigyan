import { ALL_INDIA_CRAFT_SLUG, CATEGORY_FAMILY, CATEGORY_SLUG, COMPARED_CRAFTS, CRAFT_SLUG, NOT_FOUND_PATH, UNCURATED_CRAFT_SLUG, UNKNOWN_CRAFT_SLUG } from "../production/run";

export type Marker =
  | { kind: "document"; heading: RegExp }
  | { kind: "record"; heading: RegExp }
  | { kind: "hub"; heading: RegExp }
  | { kind: "heading"; heading: RegExp }
  | { kind: "sign-in" }
  | { kind: "shell" }
  | { kind: "not-found" };

export type KeyPage = { name: string; path: string; marker: Marker; audit: boolean };

export type DrawnShape = { heading: string; chapters: number; citations: number };

export type PageSeen = {
  status: number | null;
  finalPath: string;
  drawn: boolean;
  heading: string;
  errorPanels: string[];
  shape: DrawnShape | null;
  signInFields: boolean;
  crashes: string[];
  appbars: number;
};

export const NOT_FOUND_PANEL = "error-not-found";
export const SIGN_IN_PATH = "/login";
export const NEXT_PARAM = "next";

const ANY_HEADING = /\S/;
const COMPARE_PATH = `/compare?${COMPARED_CRAFTS.map((slug) => `crafts=${slug}`).join("&")}`;

export const KEY_PAGES: readonly KeyPage[] = [
  { name: "Landing", path: "/", marker: { kind: "heading", heading: ANY_HEADING }, audit: true },
  { name: "Atlas", path: "/crafts", marker: { kind: "heading", heading: /atlas|craft/i }, audit: true },
  { name: "Kutch Ajrakh", path: `/crafts/${CRAFT_SLUG}`, marker: { kind: "document", heading: /Ajrakh/ }, audit: true },
  { name: "Bastar Dhokra", path: "/crafts/Bastar-Dhokra", marker: { kind: "document", heading: /Dhokra/ }, audit: true },
  { name: "Blue Pottery of Jaipur", path: "/crafts/Blue-Pottery-Of-Jaipur", marker: { kind: "document", heading: /Blue Pottery/i }, audit: false },
  { name: "Machilipatnam Kalamkari", path: "/crafts/Machilipatnam-Kalamkari", marker: { kind: "document", heading: /Kalamkari/ }, audit: false },
  { name: "A craft without a monograph", path: `/crafts/${UNCURATED_CRAFT_SLUG}`, marker: { kind: "record", heading: /Kasuti/ }, audit: true },
  { name: "A family", path: `/crafts/${ALL_INDIA_CRAFT_SLUG}`, marker: { kind: "document", heading: /Cane|Bamboo/i }, audit: false },
  { name: "A category hub", path: `/categories/${CATEGORY_SLUG}`, marker: { kind: "hub", heading: new RegExp(`^${CATEGORY_FAMILY}$`) }, audit: true },
  { name: "Another category hub", path: "/categories/Stone-Craft-Category", marker: { kind: "hub", heading: /^Stone$/ }, audit: false },
  { name: "Map", path: "/map", marker: { kind: "heading", heading: /map/i }, audit: true },
  { name: "Compare", path: COMPARE_PATH, marker: { kind: "heading", heading: /compare/i }, audit: false },
  { name: "Sign in", path: SIGN_IN_PATH, marker: { kind: "sign-in" }, audit: true },
  { name: "The answer page", path: "/ask", marker: { kind: "shell" }, audit: true },
  { name: "Connect an app", path: "/oauth/authorize", marker: { kind: "shell" }, audit: false },
  { name: "Connect your AI", path: "/connect", marker: { kind: "shell" }, audit: false },
  { name: "Sign up", path: "/signup", marker: { kind: "heading", heading: ANY_HEADING }, audit: false },
  { name: "Forgot password", path: "/forgot-password", marker: { kind: "heading", heading: ANY_HEADING }, audit: false },
  { name: "Privacy", path: "/privacy", marker: { kind: "heading", heading: /privacy/i }, audit: false },
  { name: "An unknown craft", path: `/crafts/${UNKNOWN_CRAFT_SLUG}`, marker: { kind: "not-found" }, audit: false },
  { name: "A page that does not exist", path: NOT_FOUND_PATH, marker: { kind: "not-found" }, audit: false }
];

export function expectedStatus(marker: Marker): number {
  return marker.kind === "not-found" ? 404 : 200;
}

export function auditPaths(asked: string | undefined = process.env.E2E_SCREEN_PATHS): string[] {
  const listed = (asked ?? "").split(",").map((path) => path.trim()).filter(Boolean);
  return listed.length ? listed : KEY_PAGES.filter((page) => page.audit).map((page) => page.path);
}

function headingProblems(what: string, heading: string, pattern: RegExp): string[] {
  if (!heading) return [`${what} draws no h1`];
  return pattern.test(heading) ? [] : [`${what} is headed "${heading}"; it should match ${pattern}`];
}

function shapeProblems(marker: Extract<Marker, { kind: "document" | "record" | "hub" }>, shape: DrawnShape | null): string[] {
  const what = { document: "the monograph", record: "the craft record", hub: "the category hub" }[marker.kind];
  if (!shape) return [`the page draws no ${what.replace(/^the /, "")}`];
  const problems = headingProblems(what, shape.heading, marker.heading);
  if (marker.kind === "document" && shape.chapters === 0) problems.push("the monograph draws no chapter");
  if (marker.kind === "document" && shape.citations === 0) problems.push("the monograph draws no citation");
  return problems;
}

export function returnsTo(finalPath: string, path: string): boolean {
  const reached = new URL(finalPath, "https://site.invalid");
  if (reached.pathname === path) return true;
  const next = reached.searchParams.get(NEXT_PARAM) ?? "";
  return reached.pathname === SIGN_IN_PATH && new URL(next, "https://site.invalid").pathname === path;
}

function markerProblems(page: KeyPage, seen: PageSeen): string[] {
  const { marker } = page;
  switch (marker.kind) {
    case "document":
    case "record":
    case "hub":
      return shapeProblems(marker, seen.shape);
    case "heading":
      return headingProblems("the page", seen.heading, marker.heading);
    case "sign-in":
      return seen.signInFields ? [] : ["the sign-in form draws no Email and Password fields"];
    case "shell":
      return returnsTo(seen.finalPath, page.path) ? [] : [`a signed-out reader ends at ${seen.finalPath}, neither ${page.path} nor sign-in on the way back to it`];
    case "not-found":
      return seen.errorPanels.includes(NOT_FOUND_PANEL) ? [] : ["the page does not show the page-not-found panel"];
  }
}

export function pageProblems(page: KeyPage, seen: PageSeen): string[] {
  const problems: string[] = [];
  const status = expectedStatus(page.marker);
  if (seen.status !== status) problems.push(seen.status === null ? "the page answered nothing" : `the page answered ${seen.status}; it should answer ${status}`);
  for (const crash of seen.crashes) problems.push(`the page threw: ${crash}`);
  if (!seen.drawn) problems.push("the page drew nothing within the wait");
  const unexpected = seen.errorPanels.filter((panel) => page.marker.kind !== "not-found" || panel !== NOT_FOUND_PANEL);
  for (const panel of unexpected) problems.push(`the page shows the ${panel} panel`);
  if (seen.appbars > 1) problems.push(`the page draws ${seen.appbars} app bars, one above the other`);
  return [...problems, ...markerProblems(page, seen)];
}
