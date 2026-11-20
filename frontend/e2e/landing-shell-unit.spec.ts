import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AuthShell } from "@/components/auth/AuthShell";
import { AuthProvider } from "@/components/AuthProvider";
import { SourcesDifferNote } from "@/components/editorial/EvidenceMark";
import { NAV_ITEMS, isNavItemVisible } from "@/components/DynamicIslandNav";
import { DNS_NAMESPACE, curatedClaimId, uuidV5 } from "@/components/landing/curatedClaim";
import { InstitutionFooter } from "@/components/landing/Footer";
import { Landing } from "@/components/landing/Landing";
import { landingCollection, type LandingCollection } from "@/components/landing/landingCollection";
import { LANDING_CRAFT_SLUG, emptyLanding, giDay, italicParts, landingContent, type LandingContent } from "@/components/landing/landingContent";
import { ACCESS_LINK, fieldsLine } from "@/components/landing/LandingHero";
import { PARTNER_MARKS, PartnersFooter } from "@/components/landing/PartnersFooter";
import { currentVatStep } from "@/components/landing/VatSteps";
import { currentHref } from "@/components/nav/Appbar";
import { publicLinks } from "@/components/nav/PublicNav";
import { ReadingBarView } from "@/components/nav/ReadingBar";
import { parseCraftCatalogue } from "@/lib/craftCatalogueContract";
import type { User } from "@/lib/types";

import { rawPage } from "./craftPageFixture";
import { FRONTEND } from "./moduleGraph";

const PAGE = rawPage();
const idOf = (key: string) => curatedClaimId(LANDING_CRAFT_SLUG, key);
const VAT_TEXT = "Cloth lifted from the indigo vat is bright green at first and turns blue as oxygen meets the dye on the fibres.";
const DEMO_TEXT = "In 2001 an earthquake that caused severe damage in Kutch almost destroyed Dhamadka, which lay only 20 km from the epicentre.";
const CATALOGUE = parseCraftCatalogue(JSON.parse(readFileSync(join(FRONTEND, "..", "shared", "craft.catalogue.golden.json"), "utf8")));

const landing = (content: LandingContent, collection: LandingCollection | null = null) =>
  renderToStaticMarkup(createElement(AuthProvider, null, createElement(Landing, { craftCount: 461, content, collection, fields: null })));
const words = (markup: string) => markup.replace(/<[^>]+>/g, " ");

test("a curated claim's id is the backend's uuid5 of its dossier key", () => {
  expect(uuidV5(DNS_NAMESPACE, "python.org")).toBe("886313e1-3b8a-5372-9b90-0c9aee199e5d");
  expect(idOf("C086")).toBe("8b628467-f530-5780-a7f3-c1661ca25abc");
  expect(PAGE.claims.find((claim) => claim.text === VAT_TEXT)?.id).toBe(idOf("C086"));
});

test("the landing reads only its photograph's label and its one worked example from Kutch Ajrakh's stored page", () => {
  const content = landingContent(PAGE, idOf);
  expect([content.name, content.family, content.place, content.craftPath]).toEqual(["Kutch Ajrakh", "Textiles · Hand block printing", "Kachchh, Gujarat", "/crafts/Kutch-Ajrakh"]);
  expect(content.vat?.text).toBe(VAT_TEXT);
  expect(content.gi?.text).toBe("Registered geographical indication, 22 April 2024");
  expect(content.demo?.text).toBe(DEMO_TEXT);
  expect(Object.keys(content).sort()).toEqual(["craftPath", "demo", "family", "gi", "name", "place", "sources", "vat"]);
  const vatSources = [...new Set(content.vat?.citations.map((citation) => citation.sourceId))];
  expect(content.sources.slice(0, vatSources.length).map((source) => source.id).sort()).toEqual(vatSources.sort());
  expect(new Set(content.sources.map((source) => source.id)).size).toBe(content.sources.length);
});

test("a botanical name is set in italic only as a whole word", () => {
  expect(italicParts("The long thin roots of Rubia cordifolia give a dye.", ["Rubia cordifolia"])).toEqual([
    { text: "The long thin roots of ", italic: false },
    { text: "Rubia cordifolia", italic: true },
    { text: " give a dye.", italic: false }
  ]);
  expect(italicParts("Tamarixes grow here.", ["Tamarix"])).toEqual([{ text: "Tamarixes grow here.", italic: false }]);
  expect(italicParts("plain", [])).toEqual([{ text: "plain", italic: false }]);
});

test("a visitor who is not signed in is led into reading, and asking and contributing are named as what access unlocks", () => {
  expect(landingContent(null, idOf)).toEqual(emptyLanding());
  const markup = landing(emptyLanding());
  expect(markup).toContain("The science in India’s crafts, <em>sourced to the sentence.</em>");
  expect(markup).toMatch(/<a [^>]*href="\/crafts"[^>]*>Explore the crafts<\/a>/);
  expect(markup).toMatch(/<a [^>]*href="\/login"[^>]*>Sign in<\/a>/);
  expect(markup).toMatch(new RegExp(`<a [^>]*href="/signup"[^>]*>${ACCESS_LINK}</a>`));
  expect(markup).not.toMatch(/data-variant="primary"[^>]*>Request access/);
  expect(markup).toContain(fieldsLine(461));
  expect(markup).not.toContain("For IIT professors");
  expect(markup).not.toContain("Chemistry, history and geography");
  expect(markup.match(/<h1/g)).toHaveLength(1);
  expect(markup).toContain('data-testid="institution-footer"');
  expect(words(markup)).not.toMatch(/loading|coming soon|no data/i);
  const preload = markup.match(/<link rel="preload" as="image"[^>]*>/)?.[0] ?? "";
  expect(preload).toContain("/_next/image?url=%2Flanding%2Fajrakh-print-detail-indigo-ground.jpg&amp;w=960&amp;q=80 960w");
  expect(preload).toContain('imageSizes="100vw"');
  expect(preload).toContain('fetchPriority="high"');
});

test("the hero names all sixteen fields' breadth and every reader, not three fields or one audience", () => {
  expect(fieldsLine(426)).toBe("Sixteen fields across 426 crafts, from materials and chemistry to ecology, history, design and policy. Every sentence opens to its source’s own words.");
  expect(fieldsLine(null)).toBe("Sixteen fields across India’s crafts, from materials and chemistry to ecology, history, design and policy. Every sentence opens to its source’s own words.");
  expect(fieldsLine(1)).toContain("across 1 craft,");
});

test("the landing is about the whole collection: monographs from every family, the families with their counts, and one labelled example", () => {
  const markup = landing(landingContent(PAGE, idOf), landingCollection(CATALOGUE));
  for (const gone of ["kv-ribbon", "One cloth, four chemistries", "kv-four", "Kachchh, home of", "place this page is about"]) expect(markup).not.toContain(gone);
  expect(markup).toContain("An example from Kutch Ajrakh");
  expect(markup).toContain("Every numeral opens a source.");
  expect(markup).toContain(DEMO_TEXT);
  expect(markup).toMatch(/data-testid="landing-documents"[\s\S]*Kutch Ajrakh[\s\S]*Bastar Dhokra/);
  expect(markup).toContain('href="/categories/Textiles-Based-Craft-Category"');
  expect(markup).toContain('href="/categories/Metal-Craft-Category"');
  expect(markup.match(/data-testid="landing-family"/g)).toHaveLength(2);
  expect(markup).toContain(">Two families of craft</h2>");
  expect(markup).toContain('id="categories"');
  expect(markup).toContain('href="#categories"');
  expect(markup.match(/data-testid="landing-stat"/g)).toHaveLength(5);
  expect(markup.match(/<h1/g)).toHaveLength(1);
  expect(markup).toContain('aria-current="step"');
  expect(markup).toContain("Photo: ");
});

test("the landing's appbar names the atlas, the map and the categories, and the reading bar keeps them at every width", () => {
  const links = publicLinks("/categories/Textiles-Based-Craft-Category");
  expect(links.map((link) => [link.label, link.href, link.current])).toEqual([
    ["Atlas", "/crafts", false],
    ["Map", "/map", false],
    ["Categories", "/crafts#atlas-index", true],
    ["Compare", "/compare", false]
  ]);
  expect(publicLinks("/crafts/Kutch-Ajrakh", "#categories").map((link) => [link.href, link.current])).toEqual([
    ["/crafts", true],
    ["/map", false],
    ["#categories", false],
    ["/compare", false]
  ]);
  const account = createElement("a", { href: "/login" }, "Sign in");
  const markup = renderToStaticMarkup(createElement(ReadingBarView, { links, account }));
  expect(markup).toMatch(/<nav class="kv-pnav" aria-label="Reading"[^>]*>.*>Atlas<.*>Map<.*>Categories<.*>Compare<.*<\/nav>/);
  expect(markup).not.toContain("max-md:hidden");
  expect(markup).not.toContain('data-testid="menu-button"');
  expect(markup).toContain('<div class="kv-bar-end" data-testid="reading-bar"><a href="/login">Sign in</a></div>');
  expect(markup).toContain('aria-current="page"');
  const nav = readFileSync(join(FRONTEND, "components", "nav", "nav.css"), "utf8");
  expect(nav).toMatch(/@media \(max-width: 639px\) \{\s*\.kv-pnav \{\s*order: 3;\s*flex-basis: 100%;/);
  expect(nav).not.toMatch(/\.kv-pnav \{[^}]*display: none/);
});

test("the appbar keeps the reading entries inline and moves tools, admin and account into the account menu", () => {
  const professor: User = { id: "p", email: "p@example.org", name: "P", role: "PROFESSOR" };
  const shown = NAV_ITEMS.filter((item) => isNavItemVisible(item, professor, false));
  expect(shown.filter((item) => item.group === null).map((item) => item.label)).toEqual(["Ask", "Crafts", "Map", "Saved"]);
  expect(NAV_ITEMS.find((item) => item.href === "/lessons")?.group).toBe("Tools");
  expect(currentHref(["/admin", "/admin/access", "/ask"], "/admin/access/requests")).toBe("/admin/access");
  expect(currentHref(["/ask"], "/asked")).toBeNull();
});

test("a disagreement reads as the board writes it: on a topic, after a colon for a quantity", () => {
  const about = renderToStaticMarkup(createElement(SourcesDifferNote, { on: true, summary: "what the colours mean" }, "Both readings."));
  expect(about).toContain("<summary>Sources differ on what the colours mean</summary>");
  const quantity = renderToStaticMarkup(createElement(SourcesDifferNote, { summary: "months, or about one month" }, "Both readings."));
  expect(quantity).toContain("<summary>Sources differ: months, or about one month</summary>");
});

test("a sign-in screen credits its photograph where it shows: under the photograph on a phone, in the label from 1024px", () => {
  const markup = renderToStaticMarkup(createElement(AuthShell, { title: "Welcome back", subtitle: "Sign in to your account" }));
  expect(markup.match(/SMarndi, CC BY-SA 4.0, via Wikimedia Commons/g)).toHaveLength(2);
  expect(markup).toContain('data-testid="auth-photo-credit"');
  expect(markup.match(/<h1/g)).toHaveLength(1);
});

test("the vat rests on blue in the air, and a GI day reads in words", () => {
  expect([currentVatStep("rest"), currentVatStep("in"), currentVatStep("lifted"), currentVatStep("air")]).toEqual(["air", "in", "lifted", "air"]);
  expect(giDay("2024-04-22")).toBe("22 April 2024");
});

test("the institution footer is one line naming IIT Kharagpur and the citation promise", () => {
  const markup = renderToStaticMarkup(createElement(InstitutionFooter));
  expect(markup).toContain("KalaVigyan, from IIT Kharagpur and its Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform. Every reader sentence is cited to a verbatim quote.");
  expect(markup.match(/<p/g)).toHaveLength(1);
});

test("the landing ends on its partners' marks, each named in its alt text and drawn from a web-weight file", () => {
  const markup = renderToStaticMarkup(createElement(PartnersFooter));
  expect(markup).toContain('data-testid="institution-footer"');
  expect(markup.replace(/<[^>]+>/g, "")).toContain("KalaVigyan, from IIT Kharagpur and its Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform.");
  expect(markup).toContain('<span class="whitespace-nowrap">AI-Enabled</span>');
  expect(markup).toContain('alt="Indian Institute of Technology Kharagpur"');
  expect(markup).toContain('alt="Development Commissioner (Handicrafts), Ministry of Textiles, Government of India"');
  expect(markup.match(/data-testid="partner-mark"/g)).toHaveLength(2);
  for (const mark of PARTNER_MARKS) {
    const file = join(FRONTEND, "public", mark.src);
    expect(existsSync(file), mark.src).toBe(true);
    expect(readFileSync(file).length, mark.src).toBeLessThan(80_000);
  }
  const svg = readFileSync(join(FRONTEND, "public", "partners", "iit-kharagpur.svg"), "utf8");
  expect(svg).not.toMatch(/<script|<metadata|on[a-z]+=/i);
  expect(svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 267.538 299.737"')).toBe(true);
  expect(readFileSync(join(FRONTEND, "public", "partners", "dc-handicrafts.webp")).subarray(8, 12).toString("latin1")).toBe("WEBP");
  const css = readFileSync(join(FRONTEND, "components", "landing", "sections.css"), "utf8");
  expect(css).toMatch(/\.kv-partner-plate \{[^}]*background-color: var\(--photo-ink-1\);/);
  expect(css).toMatch(/\.kv-partners-grid \{[^}]*justify-items: center;[^}]*text-align: center;/);
});

test("the landing's first screen carries the collection's counts once, and the collection section does not repeat them", () => {
  const markup = landing(landingContent(PAGE, idOf), landingCollection(CATALOGUE));
  expect(markup).toMatch(/data-testid="landing-hero"[\s\S]*data-testid="landing-stats"[\s\S]*data-testid="landing-collection"/);
  expect(markup.match(/data-testid="landing-stats"/g)).toHaveLength(1);
});

test("the shells sit on ground with its grain showing, and the island navigation is gone", () => {
  for (const file of ["components/shell/ShellFrame.tsx", "components/AppShell.tsx", "components/shell/ReadingShell.tsx", "components/landing/Landing.tsx", "components/auth/AuthShell.tsx"]) {
    expect(readFileSync(join(FRONTEND, file), "utf8"), file).not.toMatch(/bg-ground|bg-bg-0|backdrop-blur|GlassSurface|LiquidGlass/);
  }
  for (const gone of ["BottomIslandNav.tsx", "IslandMoreSheet.tsx", "AppSearchHeader.tsx"]) expect(existsSync(join(FRONTEND, "components", "nav", gone)), gone).toBe(false);
  for (const gone of ["ClothRibbon.tsx", "FourChemistries.tsx", "clothTile.tsx"]) expect(existsSync(join(FRONTEND, "components", "landing", gone)), gone).toBe(false);
});
