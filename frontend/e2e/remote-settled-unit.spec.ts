import { expect, test } from "@playwright/test";

import { settledFor, UNSETTLED } from "@/lib/remoteSettled";

const relief = () => Promise.resolve("relief");
const rivers = () => Promise.resolve("rivers");

test("a remote shows only what its current loader fetched in its current round", () => {
  const fetched = { load: relief, round: 0, data: "relief", failure: null };
  expect(settledFor(fetched, relief, 0)).toBe(fetched);
  expect(settledFor(fetched, rivers, 0)).toBe(UNSETTLED);
  expect(settledFor(fetched, relief, 1)).toBe(UNSETTLED);
  expect(settledFor(fetched, null, 0)).toBe(UNSETTLED);
  expect(settledFor(UNSETTLED, relief, 0)).toBe(UNSETTLED);
});

test("a failure is shown for its loader and cleared by a retry until the retry settles", () => {
  const failed = { load: rivers, round: 2, data: null, failure: { cause: new Error("offline") } };
  expect(settledFor(failed, rivers, 2).failure).toEqual({ cause: new Error("offline") });
  expect(settledFor(failed, rivers, 3)).toEqual({ load: null, round: -1, data: null, failure: null });
});
