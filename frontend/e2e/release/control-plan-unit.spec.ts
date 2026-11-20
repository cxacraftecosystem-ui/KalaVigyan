import { expect, test } from "@playwright/test";

import { shotHeight } from "../production/capture";
import { abortedRequest, webkitLeavingNoise } from "../production/checks";

import {
  citationMode,
  endsOnItsOwn,
  expectedProblems,
  flippedTheme,
  layerSwitches,
  nextDips,
  optionIndex,
  otherChoice,
  otherStep,
  switchKinds,
  unchangedProblems,
  type LayerChoice
} from "./controlPlan";
import { designedAnswer } from "./controlWatch";
import { servedSiteOrigin } from "./site";

const land = (index: number): LayerChoice => ({ kind: "land", index });
const districts = (index: number): LayerChoice => ({ kind: "districts", index });
const places: LayerChoice = { kind: "places", index: 0 };

test("the layer walk makes every kind of switch once, starting from the craft places the map opens on", () => {
  const walk = layerSwitches(3, 5);
  expect(walk).toEqual([land(0), land(1), districts(0), districts(1), places, districts(2), land(2), places]);
  expect(switchKinds(walk)).toEqual([
    "places to land",
    "land to land",
    "land to districts",
    "districts to districts",
    "districts to places",
    "places to districts",
    "districts to land",
    "land to places"
  ]);
  expect(new Set(switchKinds(walk)).size).toBe(8);
});

test("with fewer district layers the walk reuses the first and drops only the switches it cannot make", () => {
  expect(layerSwitches(3, 2)).toEqual([land(0), land(1), districts(0), districts(1), places, districts(0), land(2), places]);
  expect(layerSwitches(3, 1)).toEqual([land(0), land(1), districts(0), places, districts(0), land(2), places]);
  expect(layerSwitches(3, 0)).toEqual([land(0), land(1), places, land(2), places]);
  expect(layerSwitches(1, 2)).toEqual([land(0), districts(0), districts(1), places, districts(0), land(0), places]);
});

test("a layer's option counts the land layers first and the district layers after them", () => {
  expect(optionIndex(land(2), 3)).toBe(2);
  expect(optionIndex(districts(0), 3)).toBe(3);
  expect(optionIndex(districts(1), 3)).toBe(4);
  expect(optionIndex(places, 3)).toBeNull();
});

test("a citation opens as a sheet below 640 px and as a popover from 640 px", () => {
  expect(citationMode(360)).toBe("sheet");
  expect(citationMode(639)).toBe("sheet");
  expect(citationMode(640)).toBe("popover");
  expect(citationMode(1440)).toBe("popover");
});

test("the theme toggle, the dip player and a player's steps each move to a different state", () => {
  expect(flippedTheme("light")).toBe("dark");
  expect(flippedTheme("dark")).toBe("light");
  expect([1, 2, 3, 4].map(nextDips)).toEqual([2, 3, 4, 1]);
  expect(otherStep(1, 4)).toBe(2);
  expect(otherStep(4, 4)).toBe(1);
  expect(otherStep(1, 1)).toBeNull();
  expect(endsOnItsOwn(2, 2)).toBe(true);
  expect(endsOnItsOwn(2, 4)).toBe(false);
  expect(otherChoice(["Basic", "Detailed", "Expert"], "Detailed")).toBe("Basic");
  expect(otherChoice(["Plates", "Names"], "Plates")).toBe("Names");
  expect(otherChoice(["Plates"], "Plates")).toBeNull();
});

test("a control fails when its state is unchanged or not the state it should reach", () => {
  expect(unchangedProblems("the dip player", "2", "2")).toEqual(['the dip player left its state unchanged at "2"']);
  expect(unchangedProblems("the dip player", "2", "3")).toEqual([]);
  expect(expectedProblems("the theme toggle", "dark", "light")).toEqual(['the theme toggle shows "light"; it should show "dark"']);
  expect(expectedProblems("the theme toggle", "dark", "dark")).toEqual([]);
});

test("only a term no two crafts' cited sentences share may answer 404, as the learning contract says; every other failure counts", () => {
  expect(designedAnswer("/api/shared-science/buffalo-horn-hammer", 404)).toBe(true);
  expect(designedAnswer("/api/shared-science/alum", 500)).toBe(false);
  expect(designedAnswer("/api/crafts/Kutch-Ajrakh/shared-science", 404)).toBe(false);
  expect(designedAnswer("/api/map-layers/relief", 404)).toBe(false);
});

test("a preview reads production's API, so the API's sign-in metadata names production's site", () => {
  expect(servedSiteOrigin("https://kalavigyan-ab12cd34e-cxacraftecosystem-8028s-projects.vercel.app")).toBe("https://kalavigyan.vercel.app");
  expect(servedSiteOrigin("https://kalavigyan.vercel.app")).toBe("https://kalavigyan.vercel.app");
});

test("a request the browser dropped on leaving a page is not a failure, in Chromium, WebKit or Firefox words", () => {
  expect(abortedRequest("net::ERR_ABORTED")).toBe(true);
  expect(abortedRequest("Load request cancelled")).toBe(true);
  expect(abortedRequest("NS_BINDING_ABORTED")).toBe(true);
  expect(abortedRequest("net::ERR_CONNECTION_RESET")).toBe(false);
  expect(abortedRequest("Could not connect to the server.")).toBe(false);
});

test("WebKit's words for a fetch it dropped on leaving a page are told apart from a real failure", () => {
  const site = "https://kalavigyan-ab12cd34e-cxacraftecosystem-8028s-projects.vercel.app";
  expect(webkitLeavingNoise(`Fetch API cannot load ${site}/api/map/layers due to access control checks.`, site)).toBe(true);
  expect(webkitLeavingNoise("TypeError: Load failed", site)).toBe(true);
  expect(webkitLeavingNoise("Fetch API cannot load https: //kalavigyan-ab12cd34e-cxacraftecosystem-8028s-projects.vercel.app/ask?_rsc=1 due to access control checks.", site)).toBe(true);
  expect(webkitLeavingNoise("Unrecognized Content-Security-Policy directive 'webrtc'.\n", site)).toBe(true);
  expect(webkitLeavingNoise("Fetch API cannot load https://evil.example/x due to access control checks.", site)).toBe(false);
  expect(webkitLeavingNoise("TypeError: undefined is not an object", site)).toBe(false);
});

test("a WebKit capture keeps the first 32767 device pixels of a page taller than that", () => {
  expect(shotHeight(20_000, 3)).toBe(10_922);
  expect(shotHeight(10_922, 3)).toBeNull();
  expect(shotHeight(40_000, 1)).toBe(32_767);
  expect(shotHeight(5_000, 2)).toBeNull();
});
