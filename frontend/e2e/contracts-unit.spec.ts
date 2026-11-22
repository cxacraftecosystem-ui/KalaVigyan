import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { splitSseBuffer } from "@/lib/answerStream";
import { craftPageShape } from "@/lib/craftPageContract";
import { mediaJobShape, mediaOptionsShape } from "@/lib/mediaContract";
import { craftRegionShape, layerClassOf, mapLayerListShape, mapLayerShape } from "@/lib/regionContract";
import { parseShape, ShapeError, type Shape } from "@/lib/shape";
import {
  MAX_SPOKEN_WORDS,
  parseVoiceTurnBlock,
  voiceAvailabilityShape,
  voiceSessionEndedShape,
  voiceSessionStartedShape,
  voiceTranscriptShape
} from "@/lib/voiceContract";

const SHARED = join(__dirname, "..", "..", "shared");

function golden(name: string): unknown {
  return JSON.parse(readFileSync(join(SHARED, name), "utf8"));
}

function parsed<T>(shape: Shape<T>, name: string): T {
  return parseShape(shape, golden(name));
}

const GOLDEN: [string, Shape<unknown>][] = [
  ["craft.page.golden.json", craftPageShape],
  ["craft.page.register.golden.json", craftPageShape],
  ["region.craft.golden.json", craftRegionShape],
  ["region.layers.golden.json", mapLayerListShape],
  ["region.layer.golden.json", mapLayerShape],
  ["voice.availability.golden.json", voiceAvailabilityShape],
  ["voice.session-agent.golden.json", voiceSessionStartedShape],
  ["voice.session-relay.golden.json", voiceSessionStartedShape],
  ["voice.session-ended.golden.json", voiceSessionEndedShape],
  ["voice.transcript.golden.json", voiceTranscriptShape],
  ["media.job.golden.json", mediaJobShape],
  ["media.options.golden.json", mediaOptionsShape]
];

for (const [name, shape] of GOLDEN) {
  test(`the client parses ${name} as the backend writes it`, () => {
    expect(parseShape(shape, golden(name))).toEqual(golden(name));
  });
}

test("a field the client does not know is refused, not dropped", () => {
  const body = golden("media.options.golden.json") as Record<string, unknown>;
  expect(() => parseShape(mediaOptionsShape, { ...body, claimIds: [] })).toThrow(ShapeError);
});

test("a value outside the shared vocabulary is refused", () => {
  const job = golden("media.job.golden.json") as Record<string, unknown>;
  expect(() => parseShape(mediaJobShape, { ...job, status: "DONE" })).toThrow(/status/);
});

test("the region panel cites dataset, resolution and period for every value", () => {
  const region = parsed(craftRegionShape, "region.craft.golden.json");
  const codes = new Set(region.datasets.map((dataset) => dataset.code));
  for (const facet of region.places[0].facets) {
    for (const value of facet.values) {
      expect(codes.has(value.datasetCode)).toBe(true);
      expect(value.resolution.length).toBeGreaterThan(0);
      expect(value.period.length).toBeGreaterThan(0);
    }
  }
  expect(region.places[0]).toMatchObject({ key: "district-449", valuesFrom: "DISTRICT", inheritedReason: null });
});

test("a choropleth value falls in its class, the top class closed", () => {
  const layer = parsed(mapLayerShape, "region.layer.golden.json");
  expect(layerClassOf(layer, layer.values["444"])).toBe(0);
  expect(layerClassOf(layer, 7.08)).toBe(1);
  expect(layerClassOf(layer, layer.values["460"])).toBe(4);
  expect(() => layerClassOf(layer, 8.4)).toThrow(RangeError);
  expect(layer.boundary.caption).toBe("External boundaries of India as depicted by Survey of India. District boundaries are indicative.");
});

test("the session answer is told apart by its transport", () => {
  const agent = parsed(voiceSessionStartedShape, "voice.session-agent.golden.json");
  const relay = parsed(voiceSessionStartedShape, "voice.session-relay.golden.json");
  expect(agent.transport === "AGENT" && agent.conversationToken.length > 0).toBe(true);
  expect(relay.transport === "RELAY" && relay.audioTypes.includes("audio/webm")).toBe(true);
  const mixed = { ...(golden("voice.session-relay.golden.json") as Record<string, unknown>), conversationToken: "x" };
  expect(() => parseShape(voiceSessionStartedShape, mixed)).toThrow(ShapeError);
});

test("the relay turn stream parses into cited, short spoken turns", () => {
  const { blocks, rest } = splitSseBuffer(readFileSync(join(SHARED, "voice.turn.golden.sse"), "utf8"));
  expect(rest).toBe("");
  const events = blocks.map(parseVoiceTurnBlock);
  expect(events.map((event) => event?.type)).toEqual(["heard", "status", "source", "sentence", "action", "spoken", "done"]);
  const spoken = events.find((event) => event?.type === "spoken");
  expect(spoken?.type === "spoken" && spoken.data.text.split(/\s+/).length <= MAX_SPOKEN_WORDS).toBe(true);
  const action = events.find((event) => event?.type === "action");
  expect(action?.type === "action" && action.data.name).toBe("show_sources");
  expect(parseVoiceTurnBlock("event: transcript\ndata: {}")).toBeNull();
  expect(() => parseVoiceTurnBlock('event: action\ndata: {"name":"open_url","parameters":{}}')).toThrow(ShapeError);
});

test("a generated asset is labelled and named for KalaVigyan", () => {
  const job = parsed(mediaJobShape, "media.job.golden.json");
  expect(job.asset?.label.text).toBe("AI illustration");
  expect(job.asset?.fileName.startsWith("KalaVigyan_Generated-Image_")).toBe(true);
  expect(job.asset?.url.startsWith("https://")).toBe(true);
  expect(job.pollAfterSeconds).toBeNull();
});
