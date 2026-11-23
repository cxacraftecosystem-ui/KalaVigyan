import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CategoryHub } from "@/components/crafts/CategoryHub";
import { CollectionShelf } from "@/components/crafts/CollectionShelf";
import { wholeWordMarks } from "@/components/crafts/ConceptMatches";
import { shelfAnchor } from "@/components/crafts/HubHeader";
import { heroCredit } from "@/components/crafts/PhotoCard";
import { ledFamilyShelves, ledSubFamilyShelves } from "@/components/crafts/shelfLead";
import { familyShelves, findFamily, indexSubLine, isCatchAllKind, plateMaterial, shelfSubLine, subFamilyShelves } from "@/lib/atlasCollection";
import { allPlacesLabel, atlasDek, conceptNeighbours, monographCount, numberWord, searchHref, stateCounts, tryQueries } from "@/lib/atlasIndex";
import { namesByState, offersNamesWall, shownName, type NamedCraft } from "@/lib/atlasNames";
import { conceptDek, conceptRows, markTerms, searchStatus } from "@/lib/atlasSearch";
import { parseCraftCatalogue, type CraftCatalogue } from "@/lib/craftCatalogueContract";

const SHARED = join(__dirname, "..", "..", "shared");

function catalogue(): CraftCatalogue {
  return parseCraftCatalogue(JSON.parse(readFileSync(join(SHARED, "craft.catalogue.golden.json"), "utf8")));
}

test("each family shelf leads with its photographed monograph, then monographs, GI crafts and the rest, and never a catch-all row", () => {
  const [textiles, metal] = familyShelves(catalogue());
  expect(textiles.name).toBe("Textiles");
  expect(textiles.material).toBe("textile");
  expect(textiles.count).toBe(4);
  expect(textiles.lead?.craft.slug).toBe("Kutch-Ajrakh");
  expect(textiles.plates.map((plate) => plate.craft.slug)).toEqual(["Bagru-Hand-Block-Print", "Phulkari", "Sanganeri-Hand-Block-Printing"]);
  expect(textiles.leadEnd).toBe(false);
  expect(textiles.big).toBe(false);
  expect(metal.lead?.craft.slug).toBe("Bastar-Dhokra");
  expect(metal.plates.map((plate) => plate.craft.slug)).toEqual(["Brass-And-Bell-Metal-Craft", "Metal-Embosing"]);
  expect(metal.leadEnd).toBe(true);
  const all = [textiles, metal].flatMap((shelf) => [shelf.lead, ...shelf.plates]);
  expect(all.some((plate) => plate?.craft.slug === "Other-Hand-Block-Print")).toBe(false);
});

test("a plate's kicker names its sub-family, except a catch-all one, and its tags say monograph and GI", () => {
  const [textiles, metal] = familyShelves(catalogue());
  expect(textiles.lead?.kicker).toBe("Hand block printing");
  expect(textiles.lead?.monograph).toBe(true);
  expect(textiles.lead?.gi).toBe(true);
  const embossing = metal.plates.find((plate) => plate.craft.slug === "Metal-Embosing");
  expect(embossing?.kicker).toBeNull();
  expect(embossing?.monograph).toBe(false);
  expect(embossing?.gi).toBe(false);
  expect(isCatchAllKind({ name: "Other Textiles based Craft", label: "Textile crafts" })).toBe(true);
  expect(isCatchAllKind({ name: "Embroidery", label: "Embroidery" })).toBe(false);
});

test("the More crafts family takes painting, instrument and toy grounds by sub-family", () => {
  expect(plateMaterial("misc", "Painting")).toBe("paint");
  expect(plateMaterial("misc", "Musical instruments")).toBe("instr");
  expect(plateMaterial("misc", "Toys and figurines")).toBe("toys");
  expect(plateMaterial("misc", "Jewellery")).toBe("misc");
  expect(plateMaterial("textile", "Painting")).toBe("textile");
});

test("sub-family counts read largest first, capitalised on a shelf and in sentence case in the index", () => {
  const [textiles] = familyShelves(catalogue());
  expect(shelfSubLine(textiles.subFamilies)).toBe("Hand block printing 3 · Embroidery 1");
  expect(indexSubLine(textiles.subFamilies)).toBe("Hand block printing 3, embroidery 1");
});

test("a category hub shelves each sub-family and keeps the rest behind Show all", () => {
  const body = catalogue();
  const textiles = findFamily(body, "textiles-based-craft-category");
  if (!textiles) throw new Error("the golden catalogue has the textiles family");
  const shelves = subFamilyShelves(body, textiles);
  expect(shelves.map((shelf) => [shelf.name, shelf.count])).toEqual([
    ["Hand block printing", 3],
    ["Embroidery", 1]
  ]);
  expect(shelves[0].lead?.craft.slug).toBe("Kutch-Ajrakh");
  expect(shelves[0].plates.map((plate) => plate.craft.slug)).toEqual(["Bagru-Hand-Block-Print", "Sanganeri-Hand-Block-Printing"]);
  expect(shelves[0].more).toEqual([]);
  expect(shelves[1].lead).toBeNull();
  expect(findFamily(body, "Nowhere")).toBeNull();
});

test("a family hub indexes its sub-families beside its plate, each row a link to its own shelf", () => {
  const body = catalogue();
  const textiles = findFamily(body, "textiles-based-craft-category");
  if (!textiles) throw new Error("the golden catalogue has the textiles family");
  const html = renderToStaticMarkup(createElement(CategoryHub, { catalogue: body, category: textiles, science: null }));
  expect(html.match(/<h1/g)).toHaveLength(1);
  expect(html).toContain('aria-label="Sub-families"');
  const anchors = [...html.matchAll(/href="#(shelf-[^"]+)"/g)].map((found) => found[1]);
  expect(anchors).toHaveLength(2);
  for (const anchor of anchors) expect(html).toContain(`id="${anchor}"`);
  expect(html).toMatch(/>Hand block printing<\/span><b[^>]*>3<\/b>/);
  expect(shelfAnchor({ id: "a b/c" })).toBe("shelf-abc");
});

test("a shelf with no photographed craft leads with its first plate, so the lead and four plates fill a six-column row", () => {
  const body = catalogue();
  const [base] = familyShelves(body);
  const plate = (slug: string) => ({ ...base.plates[0], craft: { ...base.plates[0].craft, slug, id: slug } });
  const shelf = { ...base, lead: null, plates: ["a", "b", "c", "d"].map(plate), more: ["e", "f"].map(plate) };
  const [filled] = ledSubFamilyShelves([shelf]);
  expect(filled.lead?.craft.slug).toBe("a");
  expect(filled.plates.map((entry) => entry.craft.slug)).toEqual(["b", "c", "d", "e"]);
  expect(filled.more.map((entry) => entry.craft.slug)).toEqual(["f"]);
  expect(ledSubFamilyShelves([base])[0]).toBe(base);
  const textiles = findFamily(body, "textiles-based-craft-category");
  if (!textiles) throw new Error("the golden catalogue has the textiles family");
  const [, embroidery] = ledSubFamilyShelves(subFamilyShelves(body, textiles));
  expect(embroidery.lead?.craft.slug).toBe("Phulkari");
  expect(embroidery.plates).toEqual([]);
  expect(ledFamilyShelves(body).every((family) => family.lead !== null)).toBe(true);
  const html = renderToStaticMarkup(createElement(CollectionShelf, { shelf: filled, all: { expand: filled.more } }));
  expect(html.match(/data-lead="true"/g)).toHaveLength(1);
  expect(html.match(/data-testid="collection-plate"/g)).toHaveLength(5);
});

test("a hub's shelf of seven monographs fills its rows from the start, as an atlas shelf does", () => {
  const body = catalogue();
  const [textiles] = familyShelves(body);
  const plates = Array.from({ length: 6 }, (_, at) => ({ ...textiles.plates[0], href: `/crafts/m${at}`, craft: { ...textiles.plates[0].craft, id: `m${at}`, slug: `m${at}`, hero: null } }));
  const lead = textiles.lead ? { ...textiles.lead, craft: { ...textiles.lead.craft, hero: null } } : null;
  const seven = { ...textiles, id: "hub-monographs", name: "Monographs", count: 7, lead, plates, more: [], big: true };
  const grid = (html: string) => /<div id="[^"]+" class="([^"]+)"/.exec(html)?.[1] ?? "";
  const hub = renderToStaticMarkup(createElement(CollectionShelf, { shelf: seven, level: 2 }));
  const atlas = renderToStaticMarkup(createElement(CollectionShelf, { shelf: textiles, all: { href: "/categories/Textiles-Based-Craft-Category" } }));
  expect(grid(hub)).toBe(grid(atlas));
  expect(grid(hub)).not.toMatch(/justify-(center|end|between|around|evenly)|place-content|place-items/);
  expect(hub.match(/data-testid="collection-plate"/g)).toHaveLength(7);
  expect([...hub.matchAll(/href="\/crafts\/(m\d)"/g)].map((found) => found[1])).toEqual(["m0", "m1", "m2", "m3", "m4", "m5"]);
});

test("states count each reader craft once, all of India apart", () => {
  const counts = stateCounts(catalogue());
  expect(counts.states).toEqual([
    { name: "Rajasthan", count: 3 },
    { name: "Chhattisgarh", count: 1 },
    { name: "Gujarat", count: 1 },
    { name: "Haryana", count: 1 },
    { name: "Jammu and Kashmir", count: 1 },
    { name: "Punjab", count: 1 }
  ]);
  expect(counts.allIndia).toBe(2);
  expect(allPlacesLabel(counts)).toBe("Show all 6, and 2 crafts of all India");
});

test("the atlas dek counts crafts, families, states and monographs from the catalogue", () => {
  const body = catalogue();
  expect(monographCount(body)).toBe(2);
  expect(atlasDek(body)).toBe("7 crafts in two families, from 6 states and union territories. 2 are monographs, read in full.");
  expect(numberWord(9)).toBe("nine");
  expect(numberWord(12)).toBe("12");
});

test("Try offers one idea a family first, and neighbours share crafts", () => {
  const body = catalogue();
  expect(tryQueries(body)).toEqual(["indigo", "beeswax", "potassium alum", "harda"]);
  const indigo = body.concepts.find((concept) => concept.key === "indigo");
  if (!indigo) throw new Error("the golden catalogue names indigo");
  expect(conceptNeighbours(body, indigo).map((found) => [found.concept.key, found.shared])).toEqual([
    ["potassium-alum", 2],
    ["harda", 1],
    ["myrobalan", 1],
    ["printing-the-mordants", 1]
  ]);
  expect(searchHref("lost wax")).toBe("/crafts?q=lost%20wax#atlas-search");
});

test("a concept result marks a whole word or its plural, never the start of a longer word", () => {
  expect(wholeWordMarks(markTerms("Indigo blue is extracted from Indigofera tinctoria.", ["Indigo"]))).toEqual([
    { text: "Indigo", mark: true },
    { text: " blue is extracted from ", mark: false },
    { text: "Indigo", mark: false },
    { text: "fera tinctoria.", mark: false }
  ]);
  expect(wholeWordMarks(markTerms("Two mordants fix it.", ["mordant"])).filter((part) => part.mark)).toEqual([{ text: "mordant", mark: true }]);
  expect(wholeWordMarks(markTerms("The indigo", ["indigo"]))).toEqual([
    { text: "The ", mark: false },
    { text: "indigo", mark: true }
  ]);
});

test("a concept result marks the term in its cited sentence and reads its count", () => {
  expect(markTerms("Cloth lifted from the indigo vat turns blue.", ["Indigo", "neel"])).toEqual([
    { text: "Cloth lifted from the ", mark: false },
    { text: "indigo", mark: true },
    { text: " vat turns blue.", mark: false }
  ]);
  expect(markTerms("Made by the lost-wax process.", ["lost wax"]).filter((part) => part.mark)).toEqual([{ text: "lost-wax", mark: true }]);
  expect(markTerms("Nothing here names it.", [])).toEqual([{ text: "Nothing here names it.", mark: false }]);
  const crafts = catalogue().crafts.slice(1, 3);
  expect(conceptDek(conceptRows(crafts, null))).toBe("Linked to 2 crafts on the craft list.");
  expect(conceptDek(conceptRows(crafts, null), 250)).toBe("Named in the cited sentences of 250 crafts.");
  expect(searchStatus("indigo", 1, 3, "Indigo")).toBe("Indigo: 3 crafts.");
  expect(searchStatus("ajrakh", 0, 1, null)).toBe("1 craft matches.");
  expect(searchStatus(" ", 0, 0, null)).toBe("");
});

test("only a reviewed, sourced name in a known script reaches the names wall, grouped by home state", () => {
  const base = { text: "ಕಸೂತಿ", lang: "kn", script: "Knda", sourceId: "s1", sourceKind: "DOSSIER", reviewed: true };
  expect(shownName(base)).toEqual({ text: "ಕಸೂತಿ", lang: "kn", script: "Knda", sourceId: "s1", sourceKind: "dossier", reviewed: true });
  expect(shownName({ ...base, reviewed: false })).toBeNull();
  expect(shownName({ ...base, script: "Latn" })).toBeNull();
  expect(shownName({ ...base, sourceId: " " })).toBeNull();
  const named = (slug: string, state: string): NamedCraft => ({ slug, englishName: slug, state, nativeName: { text: "x", lang: "ta", script: "Taml", sourceId: "s", sourceKind: "dossier", reviewed: true } });
  const groups = namesByState([named("B", "Kerala"), named("Z", "Tamil Nadu"), named("A", "Tamil Nadu")]);
  expect(groups.map((group) => [group.state, group.crafts.map((craft) => craft.slug)])).toEqual([
    ["Tamil Nadu", ["A", "Z"]],
    ["Kerala", ["B"]]
  ]);
  expect(offersNamesWall(Array.from({ length: 5 }, (_, at) => named(String(at), "Goa")))).toBe(false);
  expect(offersNamesWall(Array.from({ length: 6 }, (_, at) => named(String(at), "Goa")))).toBe(true);
});

test("a shelf links its family hub, shows its plates and credits a Commons photograph", () => {
  const [textiles] = familyShelves(catalogue());
  const html = renderToStaticMarkup(createElement(CollectionShelf, { shelf: textiles, all: { href: "/categories/Textiles-Based-Craft-Category" } }));
  expect(html).toContain('href="/categories/Textiles-Based-Craft-Category"');
  expect(html).toContain("All 4");
  expect(html.match(/data-testid="collection-plate"/g)).toHaveLength(3);
  expect(html.match(/data-testid="photo-card"/g)).toHaveLength(1);
  expect(html).not.toContain("Other hand block printing");
  const hero = textiles.lead?.craft.hero;
  if (!hero) throw new Error("Kutch Ajrakh has a photograph in the golden catalogue");
  expect(heroCredit(hero)).toBe("Photo: Visdaviva, CC BY-SA 3.0, via Wikimedia Commons");
});
