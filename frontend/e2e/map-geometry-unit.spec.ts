import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { decodeBasemap, decodeRings, mapFrame, MAP_FRAME_DEGREES, NATURAL_EARTH_CREDIT, type NeighbourFile } from "@/components/map/basemap";
import { indiaRings, type Ring } from "@/components/map/indiaGeometry";
import { COUNTRY_LABELS, MapCanvas, RANN_LABEL } from "@/components/map/MapCanvas";
import { project } from "@/components/map/projection";
import { RANN_RINGS } from "@/components/map/rannGeometry";

import { FRONTEND } from "./moduleGraph";

const FILE = JSON.parse(readFileSync(join(FRONTEND, "public", "boundaries", "neighbours.json"), "utf8")) as NeighbourFile;
const TOKENS = readFileSync(join(FRONTEND, "app", "tokens.css"), "utf8");

type Point = { x: number; y: number };

function projectedRings(rings: readonly Ring[]): Point[][] {
  return rings.map((ring) => ring.map(([longitude, latitude]) => project(longitude, latitude)));
}

function inside(point: Point, rings: readonly Point[][]): boolean {
  let crossings = 0;
  for (const ring of rings) {
    for (let at = 0, before = ring.length - 1; at < ring.length; before = at, at += 1) {
      const a = ring[at];
      const b = ring[before];
      if (a.y > point.y !== b.y > point.y && point.x < ((b.x - a.x) * (point.y - a.y)) / (b.y - a.y) + a.x) crossings += 1;
    }
  }
  return crossings % 2 === 1;
}

const COUNTRIES = new Map(FILE.countries.map((country) => [country.iso, projectedRings(decodeRings(country.rings))]));
const INDIA = indiaRings().flatMap((polygon) => projectedRings(polygon));

function holders(longitude: number, latitude: number): string[] {
  const point = project(longitude, latitude);
  const found = [...COUNTRIES].filter(([, rings]) => inside(point, rings)).map(([iso]) => iso);
  return inside(point, INDIA) ? [...found, "IND"] : found;
}

test("known places fall in the right country once projected, and the seas in none", () => {
  expect(holders(79.861, 6.927)).toEqual(["LKA"]);
  expect(holders(90.412, 23.81)).toEqual(["BGD"]);
  expect(holders(85.324, 27.717)).toEqual(["NPL"]);
  expect(holders(89.639, 27.472)).toEqual(["BTN"]);
  expect(holders(96.159, 16.84)).toEqual(["MMR"]);
  expect(holders(91.117, 29.653)).toEqual(["CHN"]);
  expect(holders(69.177, 34.528)).toEqual(["AFG"]);
  expect(holders(67.01, 24.86)).toEqual(["PAK"]);
  expect(holders(77.209, 28.614)).toEqual(["IND"]);
  expect(holders(68, 15)).toEqual([]);
  expect(holders(88, 15)).toEqual([]);
});

test("the Survey of India boundary wins in Jammu and Kashmir and Ladakh", () => {
  expect(holders(74.308, 35.921)).toEqual(["IND"]);
  expect(holders(79.5, 35.2)).toEqual(["IND"]);
  expect(holders(73.474, 34.37)).toEqual(["IND"]);
});

test("every named neighbour is drawn and its label sits inside it", () => {
  for (const iso of ["PAK", "AFG", "CHN", "NPL", "BTN", "BGD", "MMR", "LKA"]) expect(COUNTRIES.has(iso), iso).toBe(true);
  for (const label of COUNTRY_LABELS) expect(holders(label.longitude, label.latitude), label.text).toEqual([label.key]);
  expect(FILE.licence).toBe("Public domain");
  expect(FILE.datasets.map((dataset) => dataset.dataset)).toEqual(["ne_10m_admin_0_countries_ind", "ne_10m_playas"]);
  expect(FILE.datasets.every((dataset) => /^\d+\.\d+\.\d+/.test(dataset.version) && /^[0-9a-f]{64}$/.test(dataset.sha256))).toBe(true);
  expect(NATURAL_EARTH_CREDIT).toContain("Natural Earth");
});

test("the frame holds all of India and Sri Lanka, edge to edge in sea or land", () => {
  const frame = mapFrame();
  const corners = [project(68.206, 37.082), project(97.394, 6.756), project(80.59, 5.92), project(66.1, 15.2)];
  for (const corner of corners) {
    expect(corner.x).toBeGreaterThan(frame.x);
    expect(corner.x).toBeLessThan(frame.x + frame.width);
    expect(corner.y).toBeGreaterThan(frame.y);
    expect(corner.y).toBeLessThan(frame.y + frame.height);
  }
  expect(MAP_FRAME_DEGREES.west).toBeLessThan(68.206);
  const markup = renderToStaticMarkup(createElement(MapCanvas, { title: "Map", description: "India" }));
  const rect = markup.match(/<rect x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" height="([\d.]+)" fill="var\(--map-water\)"/);
  expect(rect?.slice(1).map(Number)).toEqual([frame.x, frame.y, frame.width, frame.height]);
  expect(markup).toContain(`viewBox="${frame.x.toFixed(1)} ${frame.y.toFixed(1)} ${frame.width.toFixed(1)} ${frame.height.toFixed(1)}"`);
});

test("the Rann is Natural Earth's salt flat, never sea, and the old board's traced shapes are gone", () => {
  expect(RANN_RINGS.length).toBeGreaterThan(0);
  const rann = projectedRings(decodeRings(RANN_RINGS));
  expect(inside(project(69.2, 24.05), rann)).toBe(true);
  expect(holders(69.2, 24.05)).toEqual(["IND"]);
  expect(inside(project(70.5, 24), rann)).toBe(true);
  expect(inside(project(RANN_LABEL.longitude, RANN_LABEL.latitude), rann)).toBe(true);
  const decoded = decodeBasemap(FILE);
  expect(decoded.neighbours.map((country) => country.iso)).toEqual(FILE.countries.map((country) => country.iso));
  expect(decoded.coast.startsWith("M")).toBe(true);
  expect(decoded.borders.startsWith("M")).toBe(true);
});

function channels(name: string, block: string): number[] {
  const found = block.match(new RegExp(`--${name}: #([0-9A-F]{6});`));
  if (!found) throw new Error(`--${name} missing`);
  return [0, 2, 4].map((at) => parseInt(found[1].slice(at, at + 2), 16) / 255);
}

function oklab([r, g, b]: number[]): number[] {
  const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const [lr, lg, lb] = [lin(r), lin(g), lin(b)];
  const l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb);
  const m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb);
  const s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb);
  return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
}

function distance(a: number[], b: number[]): number {
  const [x, y] = [oklab(a), oklab(b)];
  return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]) * 100;
}

test("neighbouring land reads apart from India, the sea and the page in light and dark", () => {
  const light = TOKENS.slice(0, TOKENS.indexOf("--map-land-foreign") + 200);
  const darkStart = TOKENS.indexOf("--map-land-foreign", TOKENS.indexOf("--map-land-foreign") + 1);
  const dark = TOKENS.slice(darkStart - 200, darkStart + 200);
  const lightGround = [244, 245, 241].map((value) => value / 255);
  const darkGround = [14, 18, 28].map((value) => value / 255);
  expect(distance(channels("map-land-foreign", light), lightGround)).toBeGreaterThan(6);
  expect(distance(channels("map-land-foreign", light), channels("map-land", light))).toBeGreaterThan(3.5);
  expect(distance(channels("map-land-foreign", light), channels("map-water", light))).toBeGreaterThan(5);
  expect(distance(channels("map-land-foreign", dark), darkGround)).toBeGreaterThan(6);
  expect(distance(channels("map-land-foreign", dark), channels("map-land", dark))).toBeGreaterThan(3.5);
  expect(distance(channels("map-land-foreign", dark), channels("map-water", dark))).toBeGreaterThan(5);
});
