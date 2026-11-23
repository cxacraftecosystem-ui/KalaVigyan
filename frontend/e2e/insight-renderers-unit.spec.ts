import { expect, test } from "@playwright/test";
import { createElement } from "react";

import { BLOCK_RENDERERS } from "@/components/answer/blockRenderers";
import { ClimateRiskView } from "@/components/answer/insight/ClimateRiskView";
import { MarketGiView } from "@/components/answer/insight/MarketGiView";
import { MeasureView } from "@/components/answer/insight/MeasureView";
import { matchingTrend, median, seriesDomain, seriesPoints, theilSenIntercept, trendLine } from "@/lib/climateSeries";
import { groundwaterReading, niceCeiling, TREND_SIGNIFICANCE, trendBar, trendFinding, trendGroups } from "@/lib/climateView";
import { BLOCK_SHAPES } from "@/lib/explainerContract";
import type { ClimateRiskBlock, MarketGiBlock, MeasureBlock } from "@/lib/explainerInsight";
import { blockCitations, blockSentences } from "@/lib/explainerView";
import { factorText, giFacts, metricText, partialDateText, priceMeta } from "@/lib/insightView";
import { pText } from "@/lib/measure";
import { parseShape } from "@/lib/shape";

import { attribute, FIXED_WIDE_WIDTH, gridTracks, shownText, SHRINKABLE_TRACK, withReading } from "./explainerRender";
import { readRepo } from "./phaseBFixture";
import { phaseDBlock } from "./phaseDFixture";

const measure = () => phaseDBlock("measure", "s4.b1");
const ajrakhMarket = () => phaseDBlock("market_gi", "s5.b1");
const bagruMarket = () => phaseDBlock("market_gi", "s5.b2");
const climate = () => phaseDBlock("climate_risk", "s6.b1");
const KACHCHH = { districtLgd: 449, name: "Kachchh", stateName: "Gujarat" };

function text(html: string): string {
  return shownText(html.replace(/<[^>]+>/g, ""));
}

function regionalMeasure(): MeasureBlock {
  const block = measure();
  const row = block.rows[0];
  const citation = { ...row.sentence.citations[0], quote: "A seer of Kutch weighs 0.933 kg." };
  const conversion = {
    unit: "seer",
    metricUnit: "kg",
    factor: 0.933,
    basis: "REGIONAL",
    region: { stateLgd: 24, stateName: "Gujarat", districtLgd: 449, districtName: "Kachchh" },
    citation,
    dataset: null
  };
  const sentence = { ...row.sentence, id: "s4.b1.2", text: "A dyer of Kachchh weighs out 2 seer of alum for one bath." };
  const seer = { ...row, stated: "2 seer", low: 2, high: null, unitLabel: "seer", conversion, metric: { low: 1.87, high: null, unit: "kg" }, sentence };
  return parseShape(BLOCK_SHAPES.measure, { ...block, rows: [row, seer] });
}

function pricedMarket(): MarketGiBlock {
  const block = ajrakhMarket();
  const sentence = { ...block.gi!.sentences[0], id: "s5.b1.9", text: "Ajrakh sold for Rs 1,500 to 2,000 a metre in Bhuj in 2019." };
  const price = { stated: "Rs 1,500 to 2,000", low: 1500, high: 2000, currency: "INR", scale: null, per: "metre", pricedOn: "2019", place: "Bhuj", districtLgd: 449, sentence };
  return parseShape(BLOCK_SHAPES.market_gi, { ...block, gi: null, prices: [price] });
}

function warmingClimate(): ClimateRiskBlock {
  const block = climate();
  const temperature = {
    ...block.trends[0],
    variable: "annual_mean_temperature",
    datasetCode: "ERA5_LAND",
    mean: 26.8,
    meanUnit: "degC",
    slopePerDecade: -0.3,
    slopeUnit: "degC per decade",
    pValue: 0.31,
    significant: false
  };
  const groundwater = [
    { district: KACHCHH, datasetCode: "CGWB_LEVELS", variable: "depth_to_water", period: "2023", value: 12.5, valueText: null, unit: "m", resolution: "well" },
    { district: KACHCHH, datasetCode: "CGWB_LEVELS", variable: "stage_of_extraction", period: "2023", value: null, valueText: "Over-exploited", unit: null, resolution: "block" }
  ];
  const datasets = [...block.datasets, { ...block.datasets[0], code: "ERA5_LAND", title: "ERA5-Land monthly means" }];
  return parseShape(BLOCK_SHAPES.climate_risk, { ...block, trends: [temperature, ...block.trends], groundwater, datasets });
}

test("the insight kinds have one renderer each", () => {
  for (const kind of ["measure", "market_gi", "climate_risk"] as const) expect(BLOCK_RENDERERS[kind]).toBeDefined();
});

test("a measure shows the stated quantity, its metric value, the exact definition and its dataset row", () => {
  const block = measure();
  expect(metricText(block.rows[0])).toBe("3.05–4.57 m");
  expect(factorText(block.rows[0].conversion)).toBe("1 foot = 0.3048 m");
  expect(factorText({ ...block.rows[0].conversion, unit: "square-foot", metricUnit: "m2", factor: 0.09290304 })).toBe("1 square foot = 0.09290304 m²");
  expect(factorText({ ...block.rows[0].conversion, unit: "mile", metricUnit: "km", factor: 1.609344 })).toBe("1 mile = 1.609344 km");
  const html = withReading(createElement(MeasureView, { block }));
  expect(text(html)).toContain("10-15 feet");
  expect(text(html)).toContain("3.05–4.57 m");
  expect(text(html)).toContain("1 foot = 0.3048 m · Exact definition");
  expect(attribute(html, "measure-basis", "data-basis")).toEqual(["DEFINED"]);
  expect(attribute(html, "dataset-credit", "data-testid")).toHaveLength(1);
  expect(html).toContain("Guide for the Use of the International System of Units (SI)");
  expect(text(html)).toContain(block.rows[0].sentence.text);
  expect(html.match(/data-testid="citation-chip"/g)).toHaveLength(1);
});

test("a regional conversion names its region and cites the source that states the factor", () => {
  const block = regionalMeasure();
  expect(metricText(block.rows[1])).toBe("1.87 kg");
  const html = withReading(createElement(MeasureView, { block }));
  expect(attribute(html, "measure-basis", "data-basis")).toEqual(["DEFINED", "REGIONAL"]);
  expect(text(html)).toContain("1 seer = 0.933 kg · As stated for Kachchh, Gujarat");
  expect(attribute(html, "dataset-credit", "data-testid")).toHaveLength(1);
  expect(html.match(/data-testid="citation-chip"/g)).toHaveLength(3);
  expect(blockSentences(block)).toHaveLength(2);
  expect(blockCitations(block).at(-1)?.quote).toBe("A seer of Kutch weighs 0.933 kg.");
});

test("a GI record shows its status, registry facts, proprietors and cited sentences, with the craft's dated price beside it", () => {
  expect([partialDateText("2023-01-31"), partialDateText("2023-01"), partialDateText("2023")]).toEqual(["31 Jan 2023", "Jan 2023", "2023"]);
  expect(() => partialDateText("31-01-2023")).toThrow(RangeError);
  expect(giFacts(ajrakhMarket().gi!)).toEqual([
    { label: "Application", value: "1050" },
    { label: "Filed", value: "31 Jan 2023" },
    { label: "Registered", value: "22 Apr 2024" },
    { label: "GI Journal", value: "188" }
  ]);
  const html = withReading(createElement(MarketGiView, { block: ajrakhMarket() }));
  expect(attribute(html, "gi-status", "data-status")).toEqual(["REGISTERED"]);
  expect(text(html)).toContain("GI registered");
  expect(text(html)).toContain("Proprietor: Ajarakhpur Hastkala Vikas Sangathan");
  expect(html).toContain('href="/crafts/Kutch-Ajrakh"');
  expect(text(html)).toContain(ajrakhMarket().gi!.sentences[0].text);
  expect(html).not.toContain('data-testid="gi-imitation"');
  expect(attribute(html, "price-range", "data-testid")).toHaveLength(1);
  expect(text(html)).toContain("Rs. 7");
  expect(text(html)).toContain("Barmer · 1975");
  expect(text(html)).toContain(ajrakhMarket().prices[0].sentence.text);
  const clusters = attribute(html, "citation-chip", "data-numbers");
  expect(clusters).toHaveLength(ajrakhMarket().gi!.sentences.length + ajrakhMarket().prices.length);
  expect(clusters.flatMap((numbers) => numbers.split(","))).toHaveLength(3);
});

test("signs of imitation stand apart, and a certificate is listed when the registry states one", () => {
  const block = bagruMarket();
  expect(giFacts(block.gi!).map((fact) => `${fact.label} ${fact.value}`)).toEqual(["Application 183", "Certificate 150", "Filed 10 Aug 2009", "Registered 11 May 2011", "GI Journal 37"]);
  const html = withReading(createElement(MarketGiView, { block }));
  expect(attribute(html, "gi-imitation", "data-testid")).toHaveLength(1);
  expect(text(html)).toContain("Signs of imitation");
  expect(text(html)).toContain(block.imitation[0].text);
  expect(attribute(html, "gi-fact", "data-testid")).toHaveLength(5);
});

test("a price shows the stated range with what it is per, its place and its date; a market block with nothing is not drawn", () => {
  const block = pricedMarket();
  expect(priceMeta(block.prices[0])).toBe("Per metre · Bhuj · 2019");
  const html = withReading(createElement(MarketGiView, { block }));
  expect(html).not.toContain('data-testid="gi-status"');
  expect(attribute(html, "price-range", "data-testid")).toHaveLength(1);
  expect(text(html)).toContain("Rs 1,500 to 2,000");
  expect(text(html)).toContain("Per metre · Bhuj · 2019");
  expect(blockSentences(block).map((sentence) => sentence.id)).toEqual(["s5.b1.9"]);
  const bare = { ...block, prices: [] };
  expect(withReading(createElement(MarketGiView, { block: bare }))).toBe("");
});

test("a climate trend is drawn as its slope per decade from zero, with its significance, mean, period, resolution and dataset", () => {
  expect([niceCeiling(21.6), niceCeiling(70.760167), niceCeiling(0.3), niceCeiling(7), niceCeiling(1), niceCeiling(120), niceCeiling(0)]).toEqual([25, 100, 0.5, 10, 1, 200, 1]);
  expect(trendBar(21.6, 25)).toEqual({ left: 50, width: 43.2, rising: true });
  expect(trendBar(70.760167, 100)).toEqual({ left: 50, width: 35.38, rising: true });
  expect(trendBar(-0.3, 0.5)).toEqual({ left: 20, width: 30, rising: false });
  expect([pText(0.12), pText(0.049), pText(0.0004)]).toEqual(["p = 0.12", "p = 0.049", "p < 0.001"]);
  const block = climate();
  const html = withReading(createElement(ClimateRiskView, { block, reduce: true }));
  expect(attribute(html, "trend-chart", "data-variable")).toEqual(["annual_precipitation"]);
  expect(text(html)).toContain("Rainfall trend");
  expect(text(html)).toContain("Drier0Wetter");
  expect(attribute(html, "trend-bar", "data-left")).toEqual(["50"]);
  expect(attribute(html, "trend-bar", "data-width")).toEqual(["35.38"]);
  expect(attribute(html, "trend-bar", "data-significant")).toEqual(["true"]);
  expect(text(html)).toContain("+70.76 mm/year per decade");
  expect(text(html)).toContain("Significant · p = 0.005");
  expect(text(html)).toContain("Mean 449.36 mm/year · 1981–2025 · 0.05 degree");
  expect(text(html)).toContain(block.datasets[0].title);
  expect(text(html)).toContain("Method: Theil–Sen slope per decade; Mann–Kendall test, significant below p = 0.05");
  for (const sentence of block.meaning) expect(text(html)).toContain(sentence.text);
  expect(html.match(/data-testid="citation-chip"/g)).toHaveLength(2);
  expect(attribute(html, "trend-bar", "style").join("")).not.toContain("scaleX(0)");
  expect(text(html)).toContain("Rainfall in Kachchh has risen by 70.76 mm/year per decade");
  const moving = withReading(createElement(ClimateRiskView, { block, reduce: false }));
  expect(moving).toBe(html);
});

test("a trend chart titles its finding: one district's rise or fall, or how many districts moved significantly", () => {
  const block = warmingClimate();
  const [temperature] = trendGroups(block.trends).filter((group) => group.variable === "annual_mean_temperature");
  expect(trendFinding(temperature)).toBe("Mean temperature in Kachchh shows no significant trend");
  const rain = trendGroups(climate().trends)[0];
  const twoDistricts = { ...rain, trends: [rain.trends[0], { ...rain.trends[0], district: { ...KACHCHH, districtLgd: 450, name: "Banaskantha" }, slopePerDecade: 12, significant: false }] };
  expect(trendFinding(twoDistricts)).toBe("Rainfall has risen significantly in 1 of 2 districts");
  const none = { ...rain, trends: twoDistricts.trends.map((trend) => ({ ...trend, significant: false })) };
  expect(trendFinding(none)).toBe("Rainfall shows no significant trend in any of the 2 districts");
});

test("an annual series draws its Theil–Sen line through the median residual, on an axis from zero for rain", () => {
  expect(median([3, 1, 2])).toBe(2);
  expect(median([4, 1, 3, 2])).toBe(2.5);
  expect(() => median([])).toThrow(RangeError);
  const points = [
    { year: 2000, value: 10 },
    { year: 2001, value: 12 },
    { year: 2002, value: 30 },
    { year: 2003, value: 16 }
  ];
  expect(theilSenIntercept(points, 2)).toBe(-3990);
  expect(trendLine(points, { slopePerDecade: 20 })).toEqual({ from: { year: 2000, value: 10 }, to: { year: 2003, value: 16 } });
  expect(seriesDomain([69.47, 843.67], true)).toEqual({ low: 0, high: 1000, ticks: [0, 500, 1000] });
  expect(seriesDomain([26.06, 27.97], false)).toEqual({ low: 26, high: 28, ticks: [26, 27, 28] });
  const series = { district: KACHCHH, variable: "annual_precipitation" as const, datasetCode: "CHIRPS_3_0", unit: "mm/year", firstYear: 1981, values: [500, null, 520] };
  expect(seriesPoints(series)).toEqual([
    { year: 1981, value: 500 },
    { year: 1983, value: 520 }
  ]);
  expect(matchingTrend(series, climate().trends)?.slopePerDecade).toBe(70.760167);
  expect(matchingTrend({ ...series, variable: "annual_mean_temperature" }, climate().trends)).toBeNull();
  const drawn = withReading(createElement(ClimateRiskView, { block: { ...climate(), series: [series] } }));
  expect(attribute(drawn, "trend-series", "data-variable")).toEqual(["annual_precipitation"]);
  expect(attribute(drawn, "trend-series-trend", "data-testid")).toHaveLength(1);
  expect(text(drawn)).toContain("1983 · 520 mm/year");
  expect(text(drawn)).toContain("All 2 values");
});

test("trends are grouped by variable in a fixed order, and groundwater is shown only where a dataset gives it", () => {
  const block = warmingClimate();
  expect(trendGroups(block.trends).map((group) => [group.variable, group.domain])).toEqual([
    ["annual_precipitation", 100],
    ["annual_mean_temperature", 0.5]
  ]);
  expect([groundwaterReading(block.groundwater[0]), groundwaterReading(block.groundwater[1])]).toEqual(["12.5 m", "Over-exploited"]);
  const html = withReading(createElement(ClimateRiskView, { block, reduce: true }));
  expect(attribute(html, "trend-chart", "data-variable")).toEqual(["annual_precipitation", "annual_mean_temperature"]);
  expect(text(html)).toContain("−0.3 °C per decade");
  expect(text(html)).toContain("Not significant · p = 0.31");
  expect(attribute(html, "trend-bar", "data-significant")).toEqual(["true", "false"]);
  expect(attribute(html, "groundwater-value", "data-testid")).toHaveLength(2);
  expect(text(html)).toContain("Depth to water · Kachchh");
  expect(attribute(html, "dataset-credit", "data-testid")).toHaveLength(2);
  const empty = { ...block, trends: [], groundwater: [] };
  expect(withReading(createElement(ClimateRiskView, { block: empty, reduce: true }))).toBe("");
});

test("significance is the backend's threshold, and the fixture's trend agrees with it", () => {
  const insight = readRepo("backend", "app", "research", "blocks_climate.py");
  expect(Number(/^TREND_SIGNIFICANCE = ([\d.]+)$/m.exec(insight)?.[1])).toBe(TREND_SIGNIFICANCE);
  for (const trend of climate().trends) expect(trend.significant).toBe(trend.pValue < TREND_SIGNIFICANCE);
});

test("insight renderers lay out in shrinkable columns so nothing widens a phone page", () => {
  const html = [
    withReading(createElement(MeasureView, { block: regionalMeasure() })),
    withReading(createElement(MarketGiView, { block: bagruMarket() })),
    withReading(createElement(MarketGiView, { block: pricedMarket() })),
    withReading(createElement(ClimateRiskView, { block: warmingClimate(), reduce: false }))
  ].join("");
  const tracks = gridTracks(html);
  expect(tracks.length).toBeGreaterThan(0);
  for (const track of tracks) expect(track).toMatch(SHRINKABLE_TRACK);
  expect(html).not.toMatch(FIXED_WIDE_WIDTH);
  expect(html.match(/class="[^"]*\bmin-w-0\b/g)?.length ?? 0).toBeGreaterThan(10);
});
