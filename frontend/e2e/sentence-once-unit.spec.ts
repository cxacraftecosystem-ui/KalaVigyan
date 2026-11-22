import { expect, test } from "@playwright/test";
import { createElement } from "react";

import { MarketGiView } from "@/components/answer/insight/MarketGiView";
import { MeasureView } from "@/components/answer/insight/MeasureView";
import { TimelineMapView } from "@/components/answer/journey/TimelineMap";
import { SupplyMapView } from "@/components/answer/place/SupplyMapView";
import { BLOCK_SHAPES } from "@/lib/explainerContract";
import type { MarketGiBlock, MeasureBlock } from "@/lib/explainerInsight";
import type { SupplyLink, SupplyMapBlock } from "@/lib/explainerPlace";
import type { TimelineMapBlock } from "@/lib/explainerPlay";
import { bySentence, joinedBy, namesText, onceEach, sentenceWords } from "@/lib/sentenceGroups";
import { parseShape } from "@/lib/shape";
import { supplyLayout } from "@/lib/supplyView";
import { entryGroups, groupState, timelineEntries } from "@/lib/timelineView";

import { attribute, shownText, withApp, withReading } from "./explainerRender";
import { phaseBBlock } from "./phaseBFixture";
import { phaseDBlock } from "./phaseDFixture";
import { phaseCBlock } from "./playFixture";

const INDIA_BOX = { minLongitude: 68.206, maxLongitude: 97.394, minLatitude: 6.756, maxLatitude: 37.082 };
const JAIPUR = "The head potter's notes list locally obtained quartz stone, kach (glass), sajjt (borax), katira (gum) and Multani matt, Multan clay or fuller's earth, as the materials of Jaipur pottery.";
const AJRAKHPUR = "At Ajrakhpur water once rose at a depth of 200 feet, but an artisan's later private borewell had to reach 450 feet.";
const SHIKARPUR = "Indigo came from Shikarpur in Sindh.";
const BHUJ_ALUM = "Dyers bought alum in Bhuj.";
const DHAMADKA = "Dyers grew indigo in Dhamadka and bought madder in Bhuj.";
const PRICES = "Ajrakh sold for Rs 1,500 a metre in Bhuj in 2019 and Rs 2,200 a metre in Ahmedabad in 2019.";

const supply = () => phaseBBlock("supply_map", "s6.b1");
const unplaced = { wikidataId: null, latitude: null, longitude: null };

function count(html: string, text: string): number {
  return shownText(html.replace(/<[^>]+>/g, "")).split(text).length - 1;
}

function shown(html: string, testId: string): string[] {
  return [...html.matchAll(new RegExp(`data-testid="${testId}">([^<]+)<`, "g"))].map((found) => found[1]);
}

function linked(material: string, origin: string, id: string, text: string, place: Pick<SupplyLink, "wikidataId" | "latitude" | "longitude"> = unplaced): SupplyLink {
  const template = supply().links[0];
  return { ...template, material, materialId: null, termKey: null, origin, ...place, sentence: { ...template.sentence, id, text } };
}

function supplyOf(links: SupplyLink[]): SupplyMapBlock {
  return parseShape(BLOCK_SHAPES.supply_map, { ...supply(), links });
}

test("items that share a sentence group under it once, by the sentence's original words, in their first order", () => {
  const sentence = supply().links[0].sentence;
  const hindi = { ...sentence, id: "a", text: "पहला अनुवाद", translated: true, original: SHIKARPUR };
  const again = { ...sentence, id: "b", text: "दूसरा अनुवाद", translated: true, original: SHIKARPUR };
  const other = { ...sentence, id: "c", text: BHUJ_ALUM };
  const groups = bySentence([hindi, other, again], (item) => item);
  expect(groups.map((group) => [group.key, group.sentence.id, group.items.map((item) => item.id)])).toEqual([
    [SHIKARPUR, "a", ["a", "b"]],
    [BHUJ_ALUM, "c", ["c"]]
  ]);
  expect(onceEach([hindi, other, again]).map((said) => said.id)).toEqual(["a", "c"]);
  expect(joinedBy([["a"], ["b"], ["a", "c"], ["c", "d"], ["e"]], (keys) => keys)).toEqual([[["a"], ["a", "c"], ["c", "d"]], [["b"]], [["e"]]]);
  expect(joinedBy([["a"], ["b"], ["a", "b"]], (keys) => keys)).toEqual([[["a"], ["b"], ["a", "b"]]]);
});

test("a list of names is in sentence case, lowering a later name only where the sentences write it in lower case", () => {
  const words = sentenceWords([{ ...supply().links[0].sentence, text: JAIPUR }]);
  expect(namesText(["Quartz stone", "Kach (glass)", "Multani matt"], words)).toBe("Quartz stone, kach (glass) and Multani matt");
  expect(namesText(["quartz stone"], words)).toBe("Quartz stone");
  expect(namesText([], words)).toBe("");
});

test("materials that rest on one sentence are one row naming them in order, and the sentence is said once", () => {
  const block = supplyOf([
    linked("Quartz stone", "Jaipur", "s2.supply.1", JAIPUR),
    linked("Kach (glass)", "Jaipur", "s2.supply.2", JAIPUR),
    linked("Sajjt (borax)", "Jaipur", "s2.supply.3", JAIPUR),
    linked("Katira (gum)", "Jaipur", "s2.supply.4", JAIPUR),
    linked("Multani matt", "Multan", "s2.supply.5", JAIPUR),
    linked("Indigo", "Shikarpur", "s2.supply.6", SHIKARPUR)
  ]);
  const { groups, pins } = supplyLayout(block, INDIA_BOX);
  expect(groups.map((group) => [group.heading, group.origins.map((origin) => origin.origin), group.sentences.map((sentence) => sentence.id)])).toEqual([
    ["Quartz stone, kach (glass), sajjt (borax), katira (gum) and Multani matt", ["Jaipur", "Multan"], ["s2.supply.1"]],
    ["Indigo", ["Shikarpur"], ["s2.supply.6"]]
  ]);
  expect(pins).toEqual([]);
  const html = withReading(createElement(SupplyMapView, { block }));
  expect(attribute(html, "supply-material", "data-testid")).toHaveLength(2);
  expect(count(html, JAIPUR)).toBe(1);
  expect(count(html, SHIKARPUR)).toBe(1);
  expect(html).toContain('aria-label="Where Quartz stone, kach (glass), sajjt (borax), katira (gum) and Multani matt come from"');
  expect(html).toContain('aria-label="Where Indigo comes from"');
});

test("a material on two sentences joins the row of a material sharing either, and each place keeps one pin number in reading order", () => {
  const block = supplyOf([
    linked("Indigo", "Shikarpur", "s6.b1.1", SHIKARPUR),
    linked("Alum", "Bhuj", "s6.b1.2", BHUJ_ALUM, { wikidataId: "Q2", latitude: 23.25, longitude: 69.67 }),
    linked("Indigo", "Dhamadka", "s6.b1.3", DHAMADKA, { wikidataId: "Q1", latitude: 23.4, longitude: 70.0 }),
    linked("Madder", "Bhuj", "s6.b1.4", DHAMADKA, { wikidataId: "Q2", latitude: 23.25, longitude: 69.67 })
  ]);
  const { groups, pins } = supplyLayout(block, INDIA_BOX);
  expect(groups.map((group) => [group.heading, group.origins.map((origin) => [origin.origin, origin.pin]), group.sentences.map((sentence) => sentence.id)])).toEqual([
    ["Indigo and madder", [["Shikarpur", null], ["Dhamadka", 1], ["Bhuj", 2]], ["s6.b1.1", "s6.b1.3"]],
    ["Alum", [["Bhuj", 2]], ["s6.b1.2"]]
  ]);
  expect(pins.map((pin) => [pin.pin, pin.origin, pin.materials])).toEqual([
    [1, "Dhamadka", "Indigo"],
    [2, "Bhuj", "Madder and alum"]
  ]);
  const html = withReading(createElement(SupplyMapView, { block }));
  expect(attribute(html, "supply-pin", "data-testid")).toHaveLength(3);
  expect(html).toContain('data-testid="map-placeholder"');
  for (const text of [SHIKARPUR, BHUJ_ALUM, DHAMADKA]) expect(count(html, text)).toBe(1);
});

test("quantities one sentence states sit together under it, and the sentence is said once", () => {
  const block = phaseDBlock("measure", "s4.b1");
  const [row] = block.rows;
  const borewell = (stated: string, feet: number, metres: number, id: string) => ({ ...row, stated, low: feet, high: null, metric: { low: metres, high: null, unit: "m" }, sentence: { ...row.sentence, id, text: AJRAKHPUR } });
  const measure: MeasureBlock = parseShape(BLOCK_SHAPES.measure, { ...block, rows: [borewell("200 feet", 200, 61, "s4.b1.2"), row, borewell("450 feet", 450, 137, "s4.b1.3")] });
  const html = withReading(createElement(MeasureView, { block: measure }));
  expect(attribute(html, "measure-sentence", "data-testid")).toHaveLength(2);
  expect(attribute(html, "measure-row", "data-testid")).toHaveLength(3);
  expect(shown(html, "measure-stated")).toEqual(["200 feet", "450 feet", "10-15 feet"]);
  expect(shown(html, "measure-metric")).toEqual(["61 m", "137 m", "3.05–4.57 m"]);
  expect(count(html, AJRAKHPUR)).toBe(1);
  expect(count(html, row.sentence.text)).toBe(1);
});

test("prices one sentence states sit together under it, and the sentence is said once", () => {
  const block = phaseDBlock("market_gi", "s5.b1");
  const sentence = block.gi!.sentences[0];
  const price = (stated: string, low: number, place: string, id: string, text: string) => ({ stated, low, high: null, currency: "INR", scale: null, per: "metre", pricedOn: "2019", place, districtLgd: null, sentence: { ...sentence, id, text } });
  const prices = [price("Rs 1,500", 1500, "Bhuj", "s5.b1.9", PRICES), price("Rs 2,200", 2200, "Ahmedabad", "s5.b1.10", PRICES), price("Rs 900", 900, "Bhuj", "s5.b1.11", "A dupatta sold for Rs 900 in Bhuj in 2019.")];
  const market: MarketGiBlock = parseShape(BLOCK_SHAPES.market_gi, { ...block, gi: null, imitation: [], prices });
  const html = withReading(createElement(MarketGiView, { block: market }));
  expect(attribute(html, "price-sentence", "data-testid")).toHaveLength(2);
  expect(attribute(html, "price-range", "data-testid")).toHaveLength(3);
  expect(count(html, PRICES)).toBe(1);
  expect(count(html, "A dupatta sold for Rs 900 in Bhuj in 2019.")).toBe(1);
});

test("a point and a route one sentence states are one entry with both their years and places, said once", () => {
  const base = phaseCBlock("timeline_map", "s4.b1");
  const dhamadka = base.points[1].sentence;
  const block: TimelineMapBlock = parseShape(BLOCK_SHAPES.timeline_map, {
    ...base,
    places: base.places.map((place) => ({ ...place, ...unplaced })),
    routes: base.routes.map((route) => ({ ...route, sentence: { ...dhamadka, id: "s4.b1.4" } }))
  });
  const entries = timelineEntries(block);
  expect(entryGroups(entries).map((group) => group.items.map((entry) => entry.key))).toEqual([["point:0"], ["point:1", "route:0"], ["point:2"]]);
  expect(entryGroups(entries).map((group) => [groupState(group.items, 1586), groupState(group.items, 1700), groupState(group.items, 1401)])).toEqual([
    ["past", "past", "current"],
    ["current", "past", "later"],
    ["later", "later", "later"]
  ]);
  const html = withApp(createElement(TimelineMapView, { block, at: 1, onChoose: () => undefined }));
  expect(attribute(html, "timeline-entry", "data-state")).toEqual(["past", "current", "later"]);
  expect(attribute(html, "timeline-item", "data-kind")).toEqual(["point", "point", "route", "point"]);
  expect(shown(html, "timeline-years")).toEqual(["15th century", "1586", "1586–1631", "2001"]);
  expect(count(html, dhamadka.text)).toBe(1);
});
