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
import { Landing, atlasLine } from "@/components/landing/Landing";
import { LANDING_CRAFT_SLUG, botanicalNames, emptyLanding, giDay, italicParts, landingContent, ribbonStages, rulerWord, type LandingContent } from "@/components/landing/landingContent";
import { craftsLine } from "@/components/landing/LandingHero";
import { currentVatStep } from "@/components/landing/VatSteps";
import { currentHref } from "@/components/nav/Appbar";
import { ReadingBarView } from "@/components/nav/ReadingBar";
import type { User } from "@/lib/types";

import { rawPage } from "./craftPageFixture";
import { FRONTEND } from "./moduleGraph";

const PAGE = rawPage();
const idOf = (key: string) => curatedClaimId(LANDING_CRAFT_SLUG, key);
const VAT_TEXT = "Cloth lifted from the indigo vat is bright green at first and turns blue as oxygen meets the dye on the fibres.";
const DEMO_TEXT = "In 2001 an earthquake that caused severe damage in Kutch almost destroyed Dhamadka, which lay only 20 km from the epicentre.";

const landing = (content: LandingContent) => renderToStaticMarkup(createElement(AuthProvider, null, createElement(Landing, { craftCount: 461, content })));

test("a curated claim's id is the backend's uuid5 of its dossier key", () => {
  expect(uuidV5(DNS_NAMESPACE, "python.org")).toBe("886313e1-3b8a-5372-9b90-0c9aee199e5d");
  expect(idOf("C086")).toBe("8b628467-f530-5780-a7f3-c1661ca25abc");
  expect(PAGE.claims.find((claim) => claim.text === VAT_TEXT)?.id).toBe(idOf("C086"));
});

test("the landing reads its specimen, its four colours and its demonstration from Kutch Ajrakh's stored page", () => {
  const content = landingContent(PAGE, idOf);
  expect([content.name, content.family, content.place, content.craftPath]).toEqual(["Kutch Ajrakh", "Textiles · Hand block printing", "Kachchh, Gujarat", "/crafts/Kutch-Ajrakh"]);
  expect(content.vat?.text).toBe(VAT_TEXT);
  expect(content.gi?.text).toBe("Registered geographical indication, 22 April 2024");
  expect(content.colours.map((colour) => [colour.key, colour.sentences.length])).toEqual([
    ["blue", 1],
    ["black", 1],
    ["red", 1],
    ["white", 2]
  ]);
  expect(content.demo?.text).toBe(DEMO_TEXT);
  const vatSources = [...new Set(content.vat?.citations.map((citation) => citation.sourceId))];
  expect(content.sources.slice(0, vatSources.length).map((source) => source.id).sort()).toEqual(vatSources.sort());
  expect(new Set(content.sources.map((source) => source.id)).size).toBe(content.sources.length);
});

test("the ribbon draws Kutch Ajrakh's eleven ordered stages under their first local name, or the first word of the English name in lower case", () => {
  expect(ribbonStages(PAGE.process.stages).map((stage) => stage.label)).toEqual(["saaj", "kasanu", "rekh", "drying", "kat", "kan", "gach", "indigo", "vichharnu", "rang", "minakari"]);
  expect(ribbonStages(PAGE.process.stages).filter((stage) => !stage.local).map((stage) => stage.order)).toEqual([4, 8]);
  expect(ribbonStages(PAGE.process.stages.slice(0, 5))).toEqual([]);
  expect(rulerWord("  Drying the outline print")).toBe("drying");
});

test("a botanical name the stored stages record is set in italic wherever a landing sentence names it, and only as a whole word", () => {
  const names = botanicalNames(PAGE.process.stages);
  expect(names).toContain("Rubia cordifolia");
  expect(names).toContain("Indigofera tinctoria");
  expect(new Set(names).size).toBe(names.length);
  const red = "The long thin roots of Indian madder, Rubia cordifolia or majeeta, give a dye.";
  expect(italicParts(red, names)).toEqual([
    { text: "The long thin roots of Indian madder, ", italic: false },
    { text: "Rubia cordifolia", italic: true },
    { text: " or majeeta, give a dye.", italic: false }
  ]);
  expect(italicParts("Tamarixes grow here.", ["Tamarix"])).toEqual([{ text: "Tamarixes grow here.", italic: false }]);
  expect(italicParts("plain", [])).toEqual([{ text: "plain", italic: false }]);
  const markup = landing(landingContent(PAGE, idOf));
  expect(markup).toContain("<i>Rubia cordifolia</i>");
});

test("without the stored page the landing still stands and shows no sentence it cannot cite", () => {
  expect(landingContent(null, idOf)).toEqual(emptyLanding());
  const markup = landing(emptyLanding());
  expect(markup).toContain("The science in India’s crafts, <em>sourced to the sentence.</em>");
  expect(markup).toContain(">Request access</a>");
  expect(markup).toContain(">Sign in</a>");
  expect(markup).toContain("An atlas of 461 crafts");
  expect(markup).toContain("Chemistry, history and geography for 461 crafts.");
  expect(markup.match(/<h1/g)).toHaveLength(1);
  expect(markup).toContain('data-testid="institution-footer"');
  expect(markup).not.toContain("kv-four");
  expect(markup.replace(/<[^>]+>/g, " ")).not.toMatch(/loading|coming soon|no data/i);
  expect(markup).toContain('rel="preload" as="image" href="/landing/ajrakh-print-detail-indigo-ground.jpg" fetchPriority="high"');
});

test("the stored page fills the label, the four colours and how to read a page, each sentence cited", () => {
  const markup = landing(landingContent(PAGE, idOf));
  for (const heading of ["One cloth, four chemistries", "Every numeral opens a source."]) expect(markup).toContain(heading);
  expect(markup.match(/<h3/g)).toHaveLength(4);
  expect(markup.match(/<h1/g)).toHaveLength(1);
  expect(markup).toContain('aria-current="step"');
  expect(markup).toContain("Play again");
  expect(markup).toContain(VAT_TEXT);
  expect(markup).toContain("Photo: ");
});

test("the appbar keeps the reading entries inline and moves tools, admin and account into the account menu", () => {
  const professor: User = { id: "p", email: "p@example.org", name: "P", role: "PROFESSOR" };
  const shown = NAV_ITEMS.filter((item) => isNavItemVisible(item, professor, false));
  expect(shown.filter((item) => item.group === null).map((item) => item.label)).toEqual(["Ask", "Crafts", "Map", "Saved"]);
  expect(NAV_ITEMS.find((item) => item.href === "/lessons")?.group).toBe("Tools");
  expect(currentHref(["/admin", "/admin/access", "/ask"], "/admin/access/requests")).toBe("/admin/access");
  expect(currentHref(["/ask"], "/asked")).toBeNull();
});

test("a disagreement reads as the board writes it: on a topic for the landing's colours, after a colon for a quantity", () => {
  const about = renderToStaticMarkup(createElement(SourcesDifferNote, { on: true, summary: "what the colours mean" }, "Both readings."));
  expect(about).toContain("<summary>Sources differ on what the colours mean</summary>");
  const quantity = renderToStaticMarkup(createElement(SourcesDifferNote, { summary: "months, or about one month" }, "Both readings."));
  expect(quantity).toContain("<summary>Sources differ: months, or about one month</summary>");
  expect(landing(landingContent(PAGE, idOf))).toContain("<summary>Sources differ on what the colours mean</summary>");
});

test("below 768px the reading bar is the full wordmark and Menu alone, and signing in waits in the menu's sheet", () => {
  const links = [{ href: "/crafts", label: "Crafts", current: true }];
  const account = createElement("a", { href: "/login" }, "Sign in");
  const markup = renderToStaticMarkup(createElement(ReadingBarView, { links, account }));
  expect(markup).toContain('<span class="contents max-md:hidden"><a href="/login">Sign in</a></span>');
  expect(markup).not.toContain("sm:hidden");
  expect(markup).toContain('data-testid="menu-button"');
  expect(markup).toContain('aria-current="page"');
  expect(renderToStaticMarkup(createElement(ReadingBarView, { links, account: null }))).not.toContain("max-md:hidden");
});

test("a sign-in screen credits its photograph where it shows: under the photograph on a phone, in the label from 1024px", () => {
  const markup = renderToStaticMarkup(createElement(AuthShell, { title: "Welcome back", subtitle: "Sign in to your account" }));
  expect(markup.match(/SMarndi, CC BY-SA 4.0, via Wikimedia Commons/g)).toHaveLength(2);
  expect(markup).toContain('data-testid="auth-photo-credit"');
  expect(markup.match(/<h1/g)).toHaveLength(1);
});

test("the vat rests on blue in the air, and the copy counts only what the catalogue counts", () => {
  expect([currentVatStep("rest"), currentVatStep("in"), currentVatStep("lifted"), currentVatStep("air")]).toEqual(["air", "in", "lifted", "air"]);
  expect(giDay("2024-04-22")).toBe("22 April 2024");
  expect(atlasLine(null)).toBeNull();
  expect(atlasLine(1)).toBe("An atlas of 1 craft");
  expect(craftsLine(null)).toBe("Chemistry, history and geography for India’s crafts. Every sentence opens to its source’s own words.");
});

test("the institution footer is one line naming IIT Kharagpur and the citation promise", () => {
  const markup = renderToStaticMarkup(createElement(InstitutionFooter));
  expect(markup).toContain("KalaVigyan, from IIT Kharagpur and its Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform. Every reader sentence is cited to a verbatim quote.");
  expect(markup.match(/<p/g)).toHaveLength(1);
});

test("the shells sit on ground with its grain showing, and the island navigation is gone", () => {
  for (const file of ["components/shell/ShellFrame.tsx", "components/AppShell.tsx", "components/shell/ReadingShell.tsx", "components/landing/Landing.tsx", "components/auth/AuthShell.tsx"]) {
    expect(readFileSync(join(FRONTEND, file), "utf8"), file).not.toMatch(/bg-ground|bg-bg-0|backdrop-blur|GlassSurface|LiquidGlass/);
  }
  for (const gone of ["BottomIslandNav.tsx", "IslandMoreSheet.tsx", "AppSearchHeader.tsx"]) expect(existsSync(join(FRONTEND, "components", "nav", gone)), gone).toBe(false);
});
