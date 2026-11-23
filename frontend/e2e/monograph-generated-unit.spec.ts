import { expect, test } from "@playwright/test";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AuthProvider } from "../components/AuthProvider";
import { KitMasthead } from "../components/monograph/KitMasthead";
import { MonographPage } from "../components/monograph/MonographPage";
import { MonographSources } from "../components/monograph/MonographSources";
import { ThemeProvider } from "../components/ThemeProvider";
import { commonsThumb } from "../lib/commonsPicture";
import { citationBibtex, citationText, citeKey, versionedUrl } from "../lib/monographCite";
import { parseMonographDocument, versionedDocumentPath } from "../lib/monographDocumentShape";
import { monographMetadata } from "../lib/monographMetadata";
import { pagePlan, railChapters } from "../lib/monographRenderLayout";
import { componentPlace } from "../lib/monographScopes";
import { sourceGroups, sourceSplit, UNGRADED_GROUP } from "../lib/monographSources";

import { CAPTION, COMMONS_FILE, CREDIT, generatedDocument, HERO, LEDE, MASTHEAD_UNITS } from "./generatedMonographFixture";

const markup = (element: ReactElement) => renderToStaticMarkup(element);
const provided = (element: ReactElement) => markup(createElement(AuthProvider, null, createElement(ThemeProvider, null, element)));
const ACCESSED = new Date(2026, 10, 18, 12);

test("a generated document opens with its label: kicker, name, place, GI, the picture and the overview lede", () => {
  const plan = pagePlan(generatedDocument());
  expect(plan.label).toEqual({ kicker: "masthead-kicker", title: "masthead-title", terms: MASTHEAD_UNITS.slice(2), picture: HERO, lede: ["overview-1"] });
  expect(plan.chapters.map((chapter) => [chapter.key, chapter.number, chapter.label, chapter.blocks.length])).toEqual([
    ["opening", null, "Opening", 0],
    ["chem", 1, "The chemistry", 1],
    ["sources", 2, "Sources", 2]
  ]);
  expect(railChapters(plan).map((chapter) => chapter.key)).toEqual(["chem", "sources"]);
});

test("the masthead is the approved page's: the name over the cited lede, its tools and counts, and the label on the photograph", () => {
  const document = generatedDocument();
  const html = markup(createElement(KitMasthead, { document, label: pagePlan(document).label! }));
  expect(html.match(/<h1/g)).toHaveLength(1);
  expect(html).toContain('<header class="kv-open"><div class="kv-wrap kv-open-grid"><div class="kv-open-q"><p class="kicker kv-open-k"><span>Monograph</span></p><h1 class="kv-q">Bagh Print</h1></div>');
  expect(html).toContain('<p class="kicker">The monograph</p><p class="t-lede ans-lede"><span class="s">Bagh print is block printed on the Baghini <span class="nw">river.');
  expect(html).toContain('<div class="kv-open-act"><a class="btn" href="#kv-cite-this">Cite this monograph</a></div>');
  expect(html).toContain('<p class="kv-open-prov"><span class="kv-prov-n">Drawn from 2 sources</span>');
  expect(html).toContain('aria-label="Reliability of the 2 sources: 1 graded A, 1 graded B"');
  expect(html).not.toContain("more for the kin crafts");
  expect(html).toContain('<div class="label-card mast-label on-photo kv-open-label" data-size="title"><p class="lc-k"><span>Monograph</span><span>Textiles · Hand block printing</span></p><p class="lc-title">Bagh Print</p>');
  expect(html).toContain("<span>Registered geographical indication</span></span><span>Madhya Pradesh</span></div>");
  expect(html).toContain("/thumb/a/ab/I02.jpg/960px-I02.jpg");
  expect(html).toMatch(/<img [^>]*width="1600" height="1200" alt="Picture I02" loading="eager" fetchPriority="high"/);
  expect(html).toContain('style="object-position:50% 50%"');
  expect(html).toContain(`<figcaption><p class="cap">${CAPTION}</p><p class="credit">${CREDIT}</p></figcaption>`);
  expect(html).not.toContain('data-testid="typographic-plate"');
});

test("a generated document without a licensed photograph shows its typographic plate at the masthead", () => {
  const document = generatedDocument();
  document.content.layout = document.content.layout.filter((entry) => entry.ref !== HERO && entry.within !== HERO);
  document.content.components = [];
  document.specs = {};
  const label = pagePlan(document).label!;
  expect(label.picture).toBeNull();
  const html = markup(createElement(KitMasthead, { document, label }));
  expect(html).toContain('<div class="plate kv-open-photo"><div class="kv-open-stage"><div class="ph" data-app="">');
  expect(html).toContain('data-testid="typographic-plate"');
  expect(html).toContain("g-textile");
  expect(html).toContain('<div class="label-card mast-label on-photo kv-open-label" data-size="title">');
  expect(html).not.toContain("<figure");
});

test("the generated page draws one h1, a rail of numbered chapters without the opening, grouped sources and Cite this monograph", () => {
  const html = provided(createElement(MonographPage, { document: generatedDocument() }));
  expect(html.match(/<h1/g)).toHaveLength(1);
  expect(html).toContain('lang="en"');
  expect(html).toContain('<a href="#chem" aria-current="location"><b>1</b><span>The chemistry</span></a>');
  expect(html).toContain('<a href="#sources"><b>2</b><span>Sources</span></a>');
  expect(html).not.toContain('href="#opening"');
  expect([...html.matchAll(/<section class="kv-ch" id="([a-z-]+)"/g)].map((found) => found[1])).toEqual(["opening", "chem", "sources"]);
  expect(html).toContain('<p class="chapter-no in-main">1</p><h2 class="t-h2" id="chem-h">The chemistry</h2>');
  expect(html).toContain("<h3>Peer-reviewed or official</h3>");
  expect(html).toContain("<h3>Reputable reference</h3>");
  expect(html).toContain("The monograph’s 2 sources, numbered as they first appear.");
  expect(html).toContain('id="kv-src-status"');
  expect(html).toContain("Cite this monograph");
  expect(html).toContain("https://kalavigyan.example/crafts/bagh-print/v5");
  expect(html).toContain("KalaVigyan. “Bagh Print.” Monograph, version 5.");
});

test("sources group by reliability, the best first, and a source without a grade closes the list", () => {
  const document = generatedDocument();
  document.content.sources.g2 = { ...document.content.sources.g2, grade: null };
  expect(sourceGroups(document, sourceSplit(document).own)).toEqual([
    { title: "Peer-reviewed or official", keys: ["g1"] },
    { title: UNGRADED_GROUP, keys: ["g2"] }
  ]);
  const html = markup(createElement(MonographSources, { document }));
  expect(html.match(/class="kv-src-li"/g)).toHaveLength(2);
  expect(html).toContain("Supports 2 sentences here");
});

test("a citation names the monograph, its version, the lower-case versioned address and the day it was read", () => {
  const cite = { kind: "monograph" as const, title: "Bagh Print", version: 5, url: versionedUrl("https://kalavigyan.example/crafts/Bagh-Print/", 5), key: citeKey("Bagh-Print", 5) };
  expect(cite.url).toBe("https://kalavigyan.example/crafts/bagh-print/v5");
  expect(citationText(cite, ACCESSED)).toBe(
    "KalaVigyan. “Bagh Print.” Monograph, version 5. IIT Kharagpur, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform. https://kalavigyan.example/crafts/bagh-print/v5. Accessed 18 November 2026."
  );
  const bibtex = citationBibtex(cite, ACCESSED);
  expect(bibtex.split("\n")[0]).toBe("@misc{kalavigyan_bagh_print_v5,");
  expect(bibtex).toContain("  author = {{KalaVigyan}},");
  expect(bibtex).toContain("  urldate = {2026-11-18},");
  expect(bibtex).toContain("  howpublished = {\\url{https://kalavigyan.example/crafts/bagh-print/v5}},");
  expect(bibtex.endsWith("  note = {Monograph, version 5. Accessed 18 November 2026}\n}")).toBe(true);
  expect(citationText(cite, null).endsWith("bagh-print/v5.")).toBe(true);
});

test("a component of a generated chapter sits in the kit scope its kind is drawn in, plates in the reading column", () => {
  expect(componentPlace("reaction_player")).toEqual({ scope: "chem", frame: "wrap" });
  expect(componentPlace("picture_plate")).toEqual({ scope: "pt", frame: "column" });
  expect(componentPlace("specimen_plate")).toEqual({ scope: "mb", frame: "screen" });
  expect(componentPlace("generator")).toEqual({ scope: "rm", frame: "bare" });
  expect(componentPlace("no_such_kind")).toEqual({ scope: "mb", frame: "wrap" });
  expect(componentPlace(null)).toEqual({ scope: "mb", frame: "wrap" });
});

test("a document names its language, only a language tag parses, and an edition asks for its version", () => {
  const json = JSON.parse(JSON.stringify(generatedDocument()));
  expect(parseMonographDocument(json).language).toBe("en");
  expect(parseMonographDocument({ ...json, language: "kn-Knda" }).language).toBe("kn-Knda");
  expect(() => parseMonographDocument({ ...json, language: "English" })).toThrow(/a language tag/);
  expect(versionedDocumentPath("/crafts/Bagh-Print/monograph", 5)).toBe("/crafts/Bagh-Print/monograph?version=5");
  expect(versionedDocumentPath("/crafts/Bagh-Print/monograph", null)).toBe("/crafts/Bagh-Print/monograph");
});

test("a monograph's page shares its lede and its masthead photograph with the credit", () => {
  const metadata = monographMetadata(generatedDocument());
  expect(metadata.title).toBe("Bagh Print");
  expect(metadata.description).toBe(LEDE);
  expect(metadata.alternates?.canonical).toBe("/crafts/Bagh-Print");
  expect(metadata.openGraph?.images).toEqual([{ url: commonsThumb(COMMONS_FILE, 1280), width: 1280, alt: `${CAPTION} · ${CREDIT}` }]);
});
