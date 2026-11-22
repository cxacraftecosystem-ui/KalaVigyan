import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { simulationBlockShape } from "@/lib/explainerPlay";
import { parseShape } from "@/lib/shape";

const E2E = __dirname;
const SHARED = join(E2E, "..", "..", "shared");
const GOLDEN = /\.golden\.(json|sse)$/;
const NOT_READ_BY_SPECS = /^(production|release|capture|parity)[\\/]/;
const THIS_SPEC = "golden-files-unit.spec.ts";

const BACKEND_ONLY: Record<string, string> = {
  "voice.llm.golden.sse": "the stream the API sends the voice agent's language model host, which ElevenLabs reads",
  "voice.llm-request.golden.json": "the request ElevenLabs sends the API's custom language model route",
  "sandbox.corpus.golden.json": "the static check's corpus of generated explainer markup, read by the backend's check",
  "explainer.piece.golden.json": "a stored knowledge piece; the web reads its block inside explainer.document.golden.json",
  "science.process.golden.json": "the science process the backend's contract tests check; the web retired its process route (decision 0145)"
};

function specSources(): Map<string, string> {
  const names = readdirSync(E2E, { recursive: true, encoding: "utf8" }).filter((name) => name.endsWith(".ts") && !NOT_READ_BY_SPECS.test(name));
  return new Map(names.map((name) => [name, readFileSync(join(E2E, name), "utf8")]));
}

function readers(sources: Map<string, string>, golden: string): string[] {
  return [...sources].filter(([, source]) => source.includes(`"${golden}"`)).map(([name]) => name);
}

test("every shared golden the web reads is read by a unit spec, and every other one names who reads it", () => {
  const sources = specSources();
  const goldens = readdirSync(SHARED).filter((name) => GOLDEN.test(name));
  expect(goldens.filter((name) => !(name in BACKEND_ONLY) && readers(sources, name).length === 0)).toEqual([]);
  expect(Object.keys(BACKEND_ONLY).filter((name) => !goldens.includes(name))).toEqual([]);
  expect(Object.keys(BACKEND_ONLY).filter((name) => readers(sources, name).some((reader) => reader !== THIS_SPEC))).toEqual([]);
});

test("the craft mechanism the backend generates parses as the simulation block the web draws", () => {
  const golden = JSON.parse(readFileSync(join(SHARED, "explainer.craft-mechanism.golden.json"), "utf8")) as { block: { id: string } };
  expect(parseShape(simulationBlockShape, golden.block).id).toBe(golden.block.id);
});
