import { expect, test } from "@playwright/test";
import { createElement } from "react";

import type { CitationLookup } from "@/components/answer/CitationContext";
import { DistrictView } from "@/components/map/DistrictView";
import { listedSourceNumbers } from "@/lib/citations";
import { districtCraftsShape, type DistrictCrafts } from "@/lib/districtCraftsContract";
import type { RegionValue } from "@/lib/regionContract";
import { parseShape } from "@/lib/shape";
import { foldedRows, seriesFinding, sparkMarks, sparkPath, type YearlySeries } from "@/lib/yearlySeries";

import { attribute, shownText, withApp } from "./explainerRender";
import { readRepo } from "./phaseBFixture";

const DISTRICT = parseShape(districtCraftsShape, JSON.parse(readRepo("shared", "map.district-crafts.golden.json")));
const CHIRPS_MEANS: Array<[string, number]> = [
  ["1981", 400],
  ["1982", 120],
  ["1983", 650],
  ["1984", 300],
  ["1985", 900]
];

function climate(): RegionValue[] {
  const facet = DISTRICT.land?.facets.find((found) => found.facet === "CLIMATE");
  if (!facet) throw new Error("the golden district has a climate facet");
  return facet.values;
}

function yearly(period: string, value: number, from: Partial<RegionValue> = {}): RegionValue {
  const normal = climate().find((found) => found.datasetCode === "CHIRPS_3_0" && found.stat === "NORMAL" && found.variable === "annual_precipitation");
  if (!normal) throw new Error("the golden district has the CHIRPS normal");
  return { ...normal, period, stat: "DISTRICT_MEAN", value, ...from };
}

function withYears(values: RegionValue[]): DistrictCrafts {
  const land = DISTRICT.land;
  if (!land) throw new Error("the golden district has a land story");
  return { ...DISTRICT, land: { ...land, facets: land.facets.map((facet) => (facet.facet === "CLIMATE" ? { ...facet, values: [...facet.values, ...values] } : facet)) } };
}

function lookup(): CitationLookup {
  return { numbers: listedSourceNumbers(DISTRICT.sources), sourcesById: new Map(DISTRICT.sources.map((source) => [source.id, source])) };
}

function series(values: RegionValue[]): YearlySeries {
  const found = foldedRows(values).find((row) => row.kind === "series");
  if (!found || found.kind !== "series") throw new Error("the values fold into a series");
  return found.series;
}

test("a yearly series of one statistic folds into one row where its first year stood, and every other value stays its own row", () => {
  const means = CHIRPS_MEANS.map(([period, value]) => yearly(period, value));
  const two = [yearly("1981", 27, { datasetCode: "GHCN_CAMS_T2M", variable: "annual_mean_temperature", unit: "degC" }), yearly("1982", 28, { datasetCode: "GHCN_CAMS_T2M", variable: "annual_mean_temperature", unit: "degC" })];
  const rows = foldedRows([...climate(), ...means, ...two]);
  expect(rows.map((row) => row.kind)).toEqual([...climate().map(() => "value"), "series", "value", "value"]);
  const folded = rows[climate().length];
  expect(folded.kind === "series" ? folded.series.points : []).toEqual(CHIRPS_MEANS.map(([year, value]) => ({ year: Number(year), value })));
  const tenth = CHIRPS_MEANS.map(([period, value]) => yearly(period, value / 2, { stat: "DISTRICT_P10" }));
  expect(foldedRows([...means, ...tenth]).map((row) => row.kind)).toEqual(["series", "series"]);
});

test("the row states its finding, the highest and the lowest year, and the sparkline marks those two years in the emphasis token", () => {
  const folded = series(CHIRPS_MEANS.map(([period, value]) => yearly(period, value)));
  expect(seriesFinding(folded)).toBe("Highest 900 mm/year in 1985, lowest 120 mm/year in 1982");
  const marks = sparkMarks(folded);
  expect(marks.map((mark) => [mark.x, Number(mark.y.toFixed(1))])).toEqual([
    [4, 24.5],
    [62, 36],
    [120, 14.3],
    [178, 28.6],
    [236, 4]
  ]);
  expect(sparkPath(marks)).toBe("M4.0 24.5 L62.0 36.0 L120.0 14.3 L178.0 28.6 L236.0 4.0");
  const gap = series([yearly("1981", 400), yearly("1982", 120), yearly("1984", 900)]);
  expect(sparkPath(sparkMarks(gap)).split(" M")).toHaveLength(2);
});

test("ask the map draws the folded series with its sparkline in the rain series colour and every year in its table", () => {
  const html = withApp(createElement(DistrictView, { district: withYears(CHIRPS_MEANS.map(([period, value]) => yearly(period, value))), reduce: true, onClose: () => undefined }), lookup());
  expect(attribute(html, "yearly-series", "data-years")).toEqual(["5"]);
  expect(shownText(html)).toContain("Annual precipitation, each year 1981–1985");
  expect(shownText(html)).toContain("Highest 900 mm/year in 1985, lowest 120 mm/year in 1982");
  const row = /<div[^>]*data-testid="yearly-series"[\s\S]*?<\/details><\/dd><\/div>/.exec(html)?.[0] ?? "";
  expect(row).toContain('stroke="var(--series-rain)"');
  expect(attribute(row, "yearly-extreme", "data-year")).toEqual(["1982", "1985"]);
  expect(row).toContain('fill="var(--chart-emph)"');
  expect(row).not.toMatch(/var\(--(indigo|madder|terracotta|turmeric)/);
  expect(shownText(html)).toContain("All 5 values");
  for (const [year] of CHIRPS_MEANS) expect(html).toContain(`<th scope="row" class="px-2 py-1.5 text-start font-normal">${year}</th>`);
  expect(attribute(html, "yearly-sparkline", "aria-hidden")).toEqual(["true"]);
});
