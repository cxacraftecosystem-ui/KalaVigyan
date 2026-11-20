import { expect, test } from "@playwright/test";

import { atRest, type LiveSample } from "./parityRest";

const at = (time: number, lines: string, playing = 0): LiveSample => ({ at: time, lines, playing });

test("players are at rest once their status lines have held a second with nothing playing", () => {
  expect(atRest([at(0, "Dip 1 of 4."), at(500, "Dip 1 of 4."), at(1100, "Dip 1 of 4.")])).toBe(true);
  expect(atRest([at(0, "Lifted out: the cloth is bright green."), at(500, "In the air the cloth turns blue, from the top down."), at(1200, "In the air the cloth turns blue, from the top down.")])).toBe(false);
  expect(atRest([at(0, "Lifted out", 1), at(300, "In the air"), at(1400, "In the air")])).toBe(true);
  expect(atRest([at(0, "In the air"), at(2000, "In the air", 1)])).toBe(false);
  expect(atRest([])).toBe(false);
});
