import { expect, test } from "@playwright/test";

import {
  citationMode,
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
