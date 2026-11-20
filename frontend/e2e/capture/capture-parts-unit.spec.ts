import { expect, test } from "@playwright/test";

import { partFileName, railStops, sliceTops } from "./captureParts";

test("a long page is captured in slices of the height, at most six", () => {
  expect(sliceTops(14_500, 6000)).toEqual([0, 6000, 12_000]);
  expect(sliceTops(6000, 6000)).toEqual([0]);
  expect(sliceTops(0, 6000)).toEqual([0]);
  expect(sliceTops(100_000, 6000)).toHaveLength(6);
});

test("the rail is captured at its first, middle and last chapter", () => {
  expect(railStops(["answer", "cloth", "made", "chemistry", "sources"])).toEqual({ first: "answer", middle: "made", last: "sources" });
  expect(railStops(["glance"])).toEqual({ first: "glance", middle: "glance", last: "glance" });
  expect(railStops([])).toEqual({});
});

test("a part's picture is named after its page, its selector and its place", () => {
  expect(partFileName("crafts_Kutch-Ajrakh", ".kv-alt-comic", 0)).toBe("crafts_Kutch-Ajrakh-part-kv-alt-comic-1.png");
  expect(partFileName("crafts_Bastar-Dhokra", "dl.glance", 1)).toBe("crafts_Bastar-Dhokra-part-dl-glance-2.png");
});
