import { expect, test } from "@playwright/test";
import { createElement } from "react";

import { ExplainerSentence } from "@/components/answer/ExplainerSentence";
import { explainerSentenceShape } from "@/lib/explainerBlockBase";
import { ShapeError } from "@/lib/shape";

import { attribute, withReading } from "./explainerRender";

const PAYLOAD = {
  id: "s1.b1.1",
  text: "Alum is the mordant that binds alizarin to cotton.",
  level: "PROVISIONAL",
  citations: [
    {
      id: "c0000000-0000-4000-8000-000000000001",
      claimId: "3f2a1b0c-9d8e-4f7a-8b6c-5d4e3f2a1b0c",
      sourceId: "1a2b3c4d-0000-4000-8000-000000000001",
      quote: "Alum is the mordant",
      locator: "p. 41",
      context: null,
      evidence: "QUOTED",
      level: "PROVISIONAL"
    }
  ],
  translated: false,
  terms: []
};

test("a sentence payload may say its sources differ, and only as true or false", () => {
  expect(explainerSentenceShape.parse({ ...PAYLOAD, sourcesDiffer: true }, "sentence").sourcesDiffer).toBe(true);
  expect("sourcesDiffer" in explainerSentenceShape.parse(PAYLOAD, "sentence")).toBe(false);
  expect(() => explainerSentenceShape.parse({ ...PAYLOAD, sourcesDiffer: "yes" }, "sentence")).toThrow(ShapeError);
});

test("a sentence whose cited claim is marked sources differ draws the Sources differ tag after it", () => {
  const sentence = explainerSentenceShape.parse(PAYLOAD, "sentence");
  const flagged = withReading(createElement(ExplainerSentence, { sentence: { ...sentence, sourcesDiffer: true } }));
  expect(attribute(flagged, "evidence-tag", "data-level")).toEqual(["differ"]);
  expect(flagged).toContain("Sources differ");
  const plain = withReading(createElement(ExplainerSentence, { sentence }));
  expect(attribute(plain, "evidence-tag", "data-level")).toEqual([]);
});
