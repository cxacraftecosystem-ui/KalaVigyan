import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { PREVIEW_TOKEN, previewApiPath, previewPagePath } from "../app/(reading)/preview/[token]/previewDocument";
import { COMPONENT_VIEWS } from "../components/monograph/componentViews";
import { DECLARED_VIEWS, VIEWS } from "../components/monograph/kinds/general";
import { linePoints, tickLabel } from "../components/monograph/kinds/general/ChartLine";
import { largestValue } from "../components/monograph/kinds/general/MapLayerView";
import { axisPosition } from "../components/monograph/kinds/general/TimelineView";
import {
  chartRange,
  chartSpecShape,
  drawingSource,
  drawingSpecShape,
  drawingViewBox,
  eraYear,
  GENERAL_KINDS,
  mapLayerSpecShape,
  parsedSpec,
  placeRadius,
  share,
  tableSpecShape,
  timelineSpecShape,
  type ChartSpec
} from "../lib/componentSpecsGeneral";
import type { ComponentView } from "../lib/componentViewContract";
import type { MonographComponent } from "../lib/monographDocument";

const HEAD = { title: "u0001", caption: "u0002" };
const SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 60"><rect x="1" y="1" width="20" height="10" /></svg>';
const DRAWING = { head: HEAD, svg: SVG, alt: "u0003" };
const CHART: ChartSpec = {
  head: HEAD,
  form: "bars",
  valueLabel: "u0003",
  series: [
    {
      name: "u0004",
      points: [
        { label: "u0005", value: 50, reading: "u0006" },
        { label: "u0007", value: 100, reading: "u0008" }
      ]
    }
  ],
  emphasis: 1
};
const TABLE = {
  head: HEAD,
  columns: [
    { label: "u0003", numeric: false },
    { label: "u0004", numeric: true }
  ],
  rows: [{ cells: ["u0005", "u0006"] }, { cells: ["u0007", "u0008"] }]
};
const TIMELINE = {
  head: HEAD,
  events: [
    { year: 1868, when: "u0003", title: "u0004", text: "u0005" },
    { year: 1947, when: "u0006", title: "u0007", text: "u0008" }
  ]
};
const MAP = {
  head: HEAD,
  places: [
    { longitude: 69.67, latitude: 23.25, name: "u0003", reading: "u0004", value: 518 },
    { longitude: 75.79, latitude: 26.91, name: "u0005", reading: "u0006", value: 2072 }
  ],
  valueLabel: "u0007"
};

function component(kind: string): MonographComponent {
  return { label: `test-craft/process/${kind.replaceAll("_", "-")}`, chapter: "made", anchor: "#c", kind, title: "A component", description: "A component drawn in a test.", field: "PROCESS", fields: [], subjects: [] };
}

const GENERAL_VIEWS = { ...VIEWS, ...DECLARED_VIEWS };
const AUTHORED_TABLE = { id: "glance", numeral: 1, chapterNo: "u0001", title: "u0002", titleId: "glance-t", rows: [{ term: "u0003", value: "u0004" }] };

function render(view: ComponentView, kind: string, spec: object): string {
  const props = { component: component(kind), spec: spec as Record<string, unknown>, unitRefs: [], renderUnit: (ref: string) => `[${ref}]`, renderComponent: () => null };
  return renderToStaticMarkup(createElement(() => view(props)));
}

function drawn(kind: (typeof GENERAL_KINDS)[number], spec: object): string {
  return render(GENERAL_VIEWS[kind] as ComponentView, kind, spec);
}

test("the general group draws every general kind and the page's registry carries them", () => {
  expect(Object.keys(GENERAL_VIEWS).sort()).toEqual([...GENERAL_KINDS].sort());
  expect(COMPONENT_VIEWS.drawing).toBe(VIEWS.drawing);
  for (const kind of GENERAL_KINDS) expect(COMPONENT_VIEWS[kind]).toBeDefined();
  expect(Object.keys(COMPONENT_VIEWS).filter((kind) => kind.startsWith("general_"))).toEqual([]);
});

test("one kind per job: a declared spec draws as the site's figure and an authored spec as its own view", () => {
  const declared = render(COMPONENT_VIEWS.fact_table as ComponentView, "fact_table", TABLE);
  expect(declared).toContain('data-general="fact_table"');
  const authored = render(COMPONENT_VIEWS.fact_table as ComponentView, "fact_table", AUTHORED_TABLE);
  expect(authored).not.toContain("data-general");
  expect(authored).toContain('<dl class="glance">');
  expect(render(COMPONENT_VIEWS.chart as ComponentView, "chart", CHART)).toContain('data-general="chart"');
});

test("each general spec parses with its shape and a spec off its shape draws nothing", () => {
  expect(parsedSpec(drawingSpecShape, DRAWING)?.alt).toBe("u0003");
  expect(parsedSpec(chartSpecShape, CHART)?.series[0].points).toHaveLength(2);
  expect(parsedSpec(tableSpecShape, TABLE)?.rows).toHaveLength(2);
  expect(parsedSpec(timelineSpecShape, TIMELINE)?.events[1].year).toBe(1947);
  expect(parsedSpec(mapLayerSpecShape, MAP)?.places[0].value).toBe(518);
  expect(parsedSpec(drawingSpecShape, { ...DRAWING, svg: "<script>alert(1)</script>" })).toBeNull();
  expect(parsedSpec(mapLayerSpecShape, { ...MAP, places: [{ ...MAP.places[0], longitude: 120 }] })).toBeNull();
  expect(parsedSpec(chartSpecShape, { ...CHART, series: [] })).toBeNull();
  expect(drawn("chart", { ...CHART, form: "pie" })).toBe("");
});

test("bars are drawn at their share of the largest value from zero and the titled mark is emphasised", () => {
  expect(chartRange(CHART)).toEqual({ low: 0, high: 100 });
  expect(share(50, { low: 0, high: 100 })).toBe(0.5);
  const html = drawn("chart", CHART);
  expect(html).toContain('style="width:50.00%"');
  expect(html).toContain('data-emph="true" style="width:100.00%"');
  expect(html).toContain("[u0006]");
  expect(html).not.toContain("All 2 values");
});

test("a line is drawn across the plot with every value behind All N values", () => {
  const line = { ...CHART, form: "line" as const, emphasis: null };
  expect(linePoints(line.series[0], { low: 50, high: 100 })).toEqual([
    { x: 56, y: 196 },
    { x: 624, y: 14 }
  ]);
  expect(tickLabel(1250.5)).toBe("1,250.5");
  const html = drawn("chart", line);
  expect(html).toContain("All 2 values");
  expect(html).toContain("<polyline");
});

test("a table puts each unit in its cell, the first as the row's header, numbers aligned to the end", () => {
  const html = drawn("fact_table", TABLE);
  expect(html.match(/<th scope="col"/g)).toHaveLength(2);
  expect(html.match(/<th scope="row"/g)).toHaveLength(2);
  expect(html).toContain("text-end [font-variant-numeric:lining-nums_tabular-nums]\">[u0006]</td>");
});

test("a timeline places its events by year and names its first and last year", () => {
  expect(axisPosition(1868, 1868, 1947)).toBe(16);
  expect(axisPosition(1947, 1868, 1947)).toBe(624);
  expect(eraYear(-300)).toBe("300 BCE");
  const html = drawn("timeline", TIMELINE);
  expect(html).toContain(">1868</text>");
  expect(html).toContain(">1947</text>");
  expect(html.match(/<li /g)).toHaveLength(2);
});

test("a map layer marks each place on India's outline with a disc sized by its value and lists them", () => {
  expect(largestValue(MAP.places)).toBe(2072);
  expect(placeRadius(null, 2072)).toBe(7);
  expect(placeRadius(2072, 2072)).toBe(22);
  const html = drawn("map_layer", MAP);
  expect(html.match(/<circle /g)).toHaveLength(2);
  expect(html).not.toContain("StateLines");
  expect(html).toContain("[u0004]");
});

test("a drawing is drawn as an image of its cleaned SVG at its own aspect", () => {
  expect(drawingViewBox(SVG)).toEqual({ x: 0, y: 0, width: 120, height: 60 });
  expect(drawingSource("<svg/>")).toBe("data:image/svg+xml;charset=utf-8,%3Csvg%2F%3E");
  const html = drawn("drawing", DRAWING);
  expect(html).toContain('width="120" height="60"');
  expect(html).toContain('src="data:image/svg+xml;charset=utf-8,%3Csvg');
  expect(html).not.toContain("<rect");
});

test("a preview link is read from the API by its signed token and lives at its own page", () => {
  const token = `${"a".repeat(32)}.1795000000.${"b".repeat(64)}`;
  expect(PREVIEW_TOKEN.test(token)).toBe(true);
  expect(PREVIEW_TOKEN.test("kvpv_something")).toBe(false);
  expect(previewApiPath(token)).toBe(`/knowledge/pages/previews/${token}`);
  expect(previewPagePath(token)).toBe(`/preview/${token}`);
});
