import { expect, test } from "@playwright/test";
import { createElement } from "react";

import type { CitationLookup } from "@/components/answer/CitationContext";
import { GeneratedExplainerView } from "@/components/answer/play/GeneratedExplainer";
import { simulationBlockShape, simulationGrounded, type SimulationBlock } from "@/lib/explainerPlay";
import { parseShape, ShapeError } from "@/lib/shape";
import { sandboxData } from "@/lib/sandboxFrame";
import { keptAsPiece, wordEquation } from "@/lib/simulationView";

import { attribute, shownText, withReading } from "./explainerRender";
import { readRepo } from "./phaseBFixture";
import { phaseCBlock } from "./playFixture";

type MechanismFixture = { schemaVersion: 1; claimId: string; block: unknown; sources: { id: string }[] };

const MECHANISM = JSON.parse(readRepo("shared", "explainer.simulation-mechanism.golden.json")) as MechanismFixture;
const EQUATION = "Fe + 2 CH3COOH -> Fe(CH3COO)2 + H2";
const IRON_REACTION = "d9643f49-fefc-5e3a-ad08-a5ae499a4161";
const LOOKUP: CitationLookup = {
  numbers: new Map(MECHANISM.sources.map((source, index) => [source.id, index + 1])),
  sourcesById: new Map()
};

function mechanism(): SimulationBlock {
  return parseShape(simulationBlockShape, MECHANISM.block);
}

test("a mechanism explainer with no figure parses when its statements and stored reaction ground it", () => {
  const block = mechanism();
  expect(block.values).toEqual([]);
  expect(block.reactions?.map((reaction) => [reaction.reactionId, reaction.equation, reaction.balanced])).toEqual([[IRON_REACTION, EQUATION, true]]);
  expect(block.reactions?.[0].species.map((species) => [species.formula, species.coefficient])).toEqual([
    ["Fe", 1],
    ["CH3COOH", 2],
    ["Fe(CH3COO)2", 1],
    ["H2", 1]
  ]);
  expect(block.grounds?.map((citation) => citation.claimId)).toEqual([MECHANISM.claimId]);
  expect(simulationGrounded(block)).toBe(true);
  expect(keptAsPiece(block)).toBe(true);
  expect(sandboxData(block.values)).toBe("{}");
});

test("a generated explainer resting on nothing is refused, and an old one without the new fields still reads", () => {
  const bare = { ...(MECHANISM.block as Record<string, unknown>), grounds: undefined, reactions: undefined };
  expect(() => parseShape(simulationBlockShape, bare)).toThrow(ShapeError);
  expect(() => parseShape(simulationBlockShape, { ...(MECHANISM.block as Record<string, unknown>), grounds: [] })).toThrow(ShapeError);
  const old = phaseCBlock("simulation", "s1.b1");
  expect(Object.hasOwn(old, "grounds") || Object.hasOwn(old, "reactions")).toBe(false);
  expect(parseShape(simulationBlockShape, old).values.length).toBe(2);
});

test("built from lists the stored reaction with its equation and the statement it acts out", () => {
  const html = withReading(createElement(GeneratedExplainerView, { block: mechanism(), canHide: false, hiding: null }), LOOKUP);
  expect(attribute(html, "generated-reaction", "data-reaction")).toEqual([IRON_REACTION]);
  expect(shownText(html)).toContain("Scrap iron dissolving into iron acetate");
  expect(shownText(html)).toContain(`aria-label="${EQUATION}"`);
  expect(attribute(html, "generated-ground", "class").length).toBe(1);
  expect(shownText(html)).toContain("dyeing with indigo, madder, and iron acetate");
  expect(attribute(html, "generated-value", "data-key")).toEqual([]);
});

test("a reaction without every formula reads as a word equation", () => {
  const species = [
    { role: "REACTANT" as const, formula: "Al^3+", name: "Aluminium from the alum mordant", coefficient: null, compoundId: null },
    { role: "REACTANT" as const, formula: "C14H8O4", name: "Alizarin", coefficient: null, compoundId: null },
    { role: "PRODUCT" as const, formula: null, name: "Aluminium-alizarin lake", coefficient: null, compoundId: null }
  ];
  expect(wordEquation({ species })).toBe("Aluminium from the alum mordant + Alizarin → Aluminium-alizarin lake");
});
