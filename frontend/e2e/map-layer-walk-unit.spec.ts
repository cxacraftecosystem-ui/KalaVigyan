import { expect, test } from "@playwright/test";

import { layerWalkOrder } from "./production/screenChecks";

test("the layer walk crosses every kind of switch: land to land, land to districts, districts to districts and back to land", () => {
  expect(layerWalkOrder(3, 2)).toEqual([0, 1, 2, 3, 4, 0]);
  expect(layerWalkOrder(3, 9)).toEqual([0, 1, 2, 3, 4, 0]);
  expect(layerWalkOrder(3, 0)).toEqual([0, 1, 2, 0]);
});
