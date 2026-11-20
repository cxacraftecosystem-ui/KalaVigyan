import { expect, test } from "@playwright/test";

import { decodeBorders } from "@/components/map/borderGeometry";

test("state borders decode as lines of degrees, each a count then zigzag deltas in thousandths", () => {
  expect(decodeBorders("Ew-Bw-BofA")).toEqual([
    [
      [1, 1],
      [1.5, 1]
    ]
  ]);
  expect(decodeBorders("")).toEqual([]);
});
