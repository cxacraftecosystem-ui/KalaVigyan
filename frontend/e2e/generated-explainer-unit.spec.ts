import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AuthProvider } from "@/components/AuthProvider";
import { BLOCK_RENDERERS } from "@/components/answer/blockRenderers";
import type { CitationLookup } from "@/components/answer/CitationContext";
import { ExplainerBlockView } from "@/components/answer/ExplainerBlockView";
import { GeneratedCode } from "@/components/answer/play/GeneratedCode";
import { GeneratedExplainer, GeneratedExplainerView } from "@/components/answer/play/GeneratedExplainer";
import { SandboxFrame } from "@/components/answer/play/SandboxFrame";
import type { HidingControls } from "@/components/answer/play/useSimulationHiding";
import type { SimulationBlock, SimulationValue } from "@/lib/explainerPlay";
import { canHideGenerated } from "@/lib/permissions";
import type { RegionDataset } from "@/lib/regionContract";
import { FRAME_GUARD, FRAME_MAX_HEIGHT, FRAME_MIN_HEIGHT, FRAME_SIZER, frameHeightFrom, ownFrameHeight, sandboxData, sandboxDocument } from "@/lib/sandboxFrame";
import { ShapeError } from "@/lib/shape";
import { hiddenFrom, keptAsPiece, setSimulationHidden, simulationHiddenPath, simulationValueText, valueBases } from "@/lib/simulationView";
import type { User, UserRole } from "@/lib/types";

import { CONTENT_SECURITY_POLICY } from "../next.config";
import { attribute, shownText, withReading } from "./explainerRender";
import { readRepo } from "./phaseBFixture";
import { PHASE_C, phaseCBlock } from "./playFixture";

type Sent = { url: string; method: string | undefined; body: unknown };

const simulation = () => phaseCBlock("simulation", "s1.b1");
const WATER_SOURCE = "3cb53e85-da56-502e-8333-4fdbbb34b3ae";
const ANSWER = "6f1c2a8e-0b7d-4c3e-9f1a-2b3c4d5e6f70";
const PIECE = "0e9d8c7b-6a5f-4e3d-8c2b-1a0f9e8d7c6b";
const POLICY = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; webrtc 'block'";
const DATA = '{"fallLowFeet":10,"fallHighFeet":15}';
const LOOKUP: CitationLookup = { numbers: new Map([[WATER_SOURCE, 1]]), sourcesById: new Map() };
const RAIN_ROW: RegionDataset = {
  code: "CHIRPS_2_0",
  title: "CHIRPS rainfall",
  publisher: null,
  edition: "2.0",
  period: "1991-2020",
  nativeResolution: "0.05 degree",
  licence: "CC0",
  licenceUrl: null,
  attribution: null,
  citation: null,
  url: null
};
const RAIN: SimulationValue = { key: "rainMm", label: "Mean yearly rainfall", value: 340, unit: "mm", stated: null, citations: [], datasetCode: "CHIRPS_2_0" };

function controls(hidden: boolean): HidingControls {
  return { hidden, busy: false, failed: false, change: () => undefined };
}

function view(block: SimulationBlock, canHide: boolean, hiding: HidingControls | null): string {
  return withReading(createElement(GeneratedExplainerView, { block, canHide, hiding }), LOOKUP);
}

function frameAttributes(html: string): Record<string, string> {
  const tag = /<iframe\b[^>]*>/.exec(html)?.[0] ?? "";
  return Object.fromEntries([...tag.matchAll(/\s([a-zA-Z-]+)="([^"]*)"/g)].map((found) => [found[1].toLowerCase(), shownText(found[2])]));
}

async function withFetch<T>(answer: unknown, run: () => Promise<T>): Promise<{ result: T; sent: Sent[] }> {
  const sent: Sent[] = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    sent.push({ url: String(input), method: init?.method, body: init?.body ? JSON.parse(String(init.body)) : null });
    return new Response(JSON.stringify(answer), { headers: { "content-type": "application/json" } });
  };
  try {
    return { result: await run(), sent };
  } finally {
    globalThis.fetch = realFetch;
  }
}

test("the generated explainer is drawn through the renderer registry", () => {
  expect(BLOCK_RENDERERS.simulation).toBe(GeneratedExplainer);
});

test("the frame document opens with the plan's policy and hands the code its values as data only", () => {
  const block = simulation();
  expect(PHASE_C.sandbox.csp).toBe(POLICY);
  expect(sandboxData(block.values)).toBe(DATA);
  expect(sandboxDocument(block.html, block.values)).toBe(
    `<!doctype html><html lang="en"><head><meta http-equiv="Content-Security-Policy" content="${POLICY}"><meta charset="utf-8">` +
      `<meta name="viewport" content="width=device-width, initial-scale=1"><script type="application/json" id="kv-data">${DATA}</script>` +
      `<script>${FRAME_GUARD}</script><script>${FRAME_SIZER}</script></head><body>${block.html}</body></html>`
  );
  expect(block.html).toContain(`document.getElementById("${PHASE_C.sandbox.dataElementId}")`);
  expect(() => sandboxData([{ key: "fall", value: 1 }, { key: "fall", value: 2 }])).toThrow(RangeError);
  expect(() => sandboxData([{ key: "fall", value: Number.NaN }])).toThrow(RangeError);
});

test("the frame grants scripts only, carries its document in srcdoc and is titled", () => {
  const block = simulation();
  const frame = frameAttributes(renderToStaticMarkup(createElement(SandboxFrame, { block })));
  expect(Object.keys(frame).sort()).toEqual(["class", "data-testid", "sandbox", "srcdoc", "style", "title"]);
  expect(frame.sandbox).toBe("allow-scripts");
  expect(frame.sandbox).toBe(PHASE_C.sandbox.attribute);
  expect(frame.srcdoc).toBe(sandboxDocument(block.html, block.values));
  expect(frame.srcdoc.startsWith(`<!doctype html><html lang="en"><head><meta http-equiv="Content-Security-Policy" content="${POLICY}">`)).toBe(true);
  expect(frame.title).toBe("How fast the water table falls");
  expect(frame.style).toBe("height:360px");
});

test("the page takes only a bounded height, and only from its own frame", () => {
  expect([FRAME_MIN_HEIGHT, FRAME_MAX_HEIGHT]).toEqual([120, 1200]);
  expect(frameHeightFrom({ kvFrameHeight: 512.2 })).toBe(513);
  expect(frameHeightFrom({ kvFrameHeight: 4 })).toBe(120);
  expect(frameHeightFrom({ kvFrameHeight: 90000 })).toBe(1200);
  const refused = [null, 512, "512", [512], {}, { height: 512 }, { kvFrameHeight: "512" }, { kvFrameHeight: Number.NaN }, { kvFrameHeight: Number.POSITIVE_INFINITY }, { kvFrameHeight: 512, run: "x" }];
  for (const message of refused) expect(frameHeightFrom(message)).toBeNull();
  const own = {};
  expect(ownFrameHeight({ source: own, data: { kvFrameHeight: 300 } }, own)).toBe(300);
  expect(ownFrameHeight({ source: {}, data: { kvFrameHeight: 300 } }, own)).toBeNull();
  expect(ownFrameHeight({ source: null, data: { kvFrameHeight: 300 } }, null)).toBeNull();
  expect(ownFrameHeight({ source: undefined, data: { kvFrameHeight: 300 } }, undefined)).toBeNull();
});

test("View code shows the fragment as text and never as markup", () => {
  const block = simulation();
  const html = renderToStaticMarkup(createElement(GeneratedCode, { id: "s1.b1-code", html: block.html }));
  expect(html.startsWith('<pre id="s1.b1-code"')).toBe(true);
  expect(html).not.toMatch(/<(script|style|div|input|label|output|p)\b/);
  expect(html).toContain("&lt;script&gt;");
  expect(shownText(/<code>([\s\S]*)<\/code>/.exec(html)?.[1] ?? "")).toBe(block.html);
});

test("the explainer is labelled with its model and date and lists what it was built from with citations", () => {
  const html = view(simulation(), false, null);
  expect(shownText(html.replace(/<[^>]+>/g, ""))).toContain("Generated explainer · claude-opus-5-5 · 18 Nov 2026");
  expect(html).not.toMatch(/<(script|style)\b/);
  expect(html.match(/<iframe\b/g)).toHaveLength(1);
  expect(attribute(html, "generated-value", "data-key")).toEqual(["fallLowFeet", "fallHighFeet"]);
  expect(html).toContain(">10 feet a year<");
  expect(html).toContain(">15 feet a year<");
  expect(html.match(/<q>10-15 feet every year<\/q>/g)).toHaveLength(2);
  expect(html.match(/data-testid="citation-chip"/g)).toHaveLength(2);
  expect(attribute(html, "citation-chip", "data-numbers")).toEqual(["1", "1"]);
  expect(attribute(html, "generated-view-code", "aria-expanded")).toEqual(["false"]);
  expect(html).not.toContain("aria-controls");
  expect(html).not.toContain('data-testid="generated-code"');
  expect(html).not.toContain('data-testid="generated-hide"');
  expect([
    simulationValueText({ value: 10, unit: "feet a year" }),
    simulationValueText({ value: -2.5, unit: "degC" }),
    simulationValueText({ value: 12.5, unit: "%" }),
    simulationValueText({ value: 7, unit: null })
  ]).toEqual(["10 feet a year", "−2.5 °C", "12.5%", "7"]);
});

test("a value is drawn only on its quoted words or its dataset row, and a block with any other is not drawn", () => {
  const block = simulation();
  expect(valueBases(block)).toEqual([
    { kind: "stated", stated: "10-15 feet every year" },
    { kind: "stated", stated: "10-15 feet every year" }
  ]);
  expect(valueBases({ values: [RAIN], datasets: [RAIN_ROW] })).toEqual([{ kind: "dataset", dataset: RAIN_ROW }]);
  expect(valueBases({ values: [RAIN], datasets: [] })).toBeNull();
  expect(valueBases({ values: [{ ...RAIN, stated: "340 mm" }], datasets: [RAIN_ROW] })).toBeNull();
  expect(valueBases({ values: [{ ...RAIN, citations: block.values[0].citations }], datasets: [RAIN_ROW] })).toBeNull();
  expect(valueBases({ values: [{ ...block.values[0], citations: [] }], datasets: [] })).toBeNull();
  expect(valueBases({ values: [block.values[0], block.values[0]], datasets: [] })).toBeNull();
  expect(view({ ...block, values: [{ ...block.values[0], datasetCode: "CHIRPS_2_0" }] }, true, controls(false))).toBe("");
  const fromRow = view({ ...block, values: [RAIN], datasets: [RAIN_ROW] }, false, null);
  expect(fromRow).toContain('data-testid="dataset-credit"');
  expect(fromRow).toContain(">340 mm<");
  expect(fromRow).not.toContain('data-testid="citation-chip"');
});

test("Professors and above hide a generated explainer; a hidden one is collapsed for them and not drawn for anyone else", () => {
  const person = (role: UserRole): User => ({ id: role, email: `${role}@example.org`, name: role, role });
  const ladder = ["STUDENT", "RESEARCHER", "PROFESSOR", "ADMIN", "MASTER_ADMIN"] as const;
  expect(ladder.map((role) => canHideGenerated(person(role)))).toEqual([false, false, true, true, true]);
  expect(canHideGenerated(null)).toBe(false);
  const block = simulation();
  const hidden = { ...block, hidden: true };
  expect(view(block, true, controls(false))).toContain('data-testid="generated-hide"');
  expect(view(hidden, false, null)).toBe("");
  const collapsed = view(hidden, true, controls(true));
  expect(attribute(collapsed, "generated-explainer", "data-hidden")).toEqual(["true"]);
  expect(collapsed).toContain('data-testid="generated-show"');
  expect(collapsed).not.toContain("<iframe");
  expect(collapsed).not.toContain('data-testid="generated-view-code"');
  expect(attribute(view(block, true, controls(true)), "generated-explainer", "data-hidden")).toEqual(["true"]);
  expect(view(hidden, true, null)).not.toContain('data-testid="generated-show"');
  expect(view(block, true, { ...controls(false), failed: true })).toContain('role="alert"');
});

test("hiding asks the contract's route and refuses an answer about another block or state", async () => {
  const route = /`PUT (\/api\/answers\/\{answerId\}\/simulations\/\{blockId\}\/hidden)`/.exec(readRepo("docs", "contracts", "explainer.md"))?.[1];
  expect(`/api${simulationHiddenPath(ANSWER, "s1.b1")}`).toBe(route?.replace("{answerId}", ANSWER).replace("{blockId}", "s1.b1"));
  const answer = { answerId: ANSWER, blockId: "s1.b1", pieceId: PIECE, hidden: true };
  const { result, sent } = await withFetch(answer, () => setSimulationHidden(ANSWER, "s1.b1", true));
  expect(result).toEqual(answer);
  expect(sent).toEqual([{ url: `/api/answers/${ANSWER}/simulations/s1.b1/hidden`, method: "PUT", body: { hidden: true } }]);
  await expect(withFetch({ ...answer, blockId: "s2.b1" }, () => setSimulationHidden(ANSWER, "s1.b1", true))).rejects.toThrow(ShapeError);
  await expect(withFetch({ ...answer, hidden: false }, () => setSimulationHidden(ANSWER, "s1.b1", true))).rejects.toThrow(ShapeError);
  await expect(withFetch({ ...answer, pieceId: "piece" }, () => setSimulationHidden(ANSWER, "s1.b1", true))).rejects.toThrow(ShapeError);
});

test("Hide is offered only for an explainer kept as a piece, and a hidden one leaves no slot for readers", () => {
  const block = simulation();
  expect(keptAsPiece(block)).toBe(true);
  expect(keptAsPiece({ ...block, values: [RAIN] })).toBe(false);
  expect(keptAsPiece({ ...block, values: [RAIN], reuse: { pieceId: PIECE, storedAt: "2026-11-17T09:00:00Z" } })).toBe(true);
  expect([hiddenFrom({ ...block, hidden: true }, false), hiddenFrom({ ...block, hidden: true }, true), hiddenFrom(block, false)]).toEqual([true, false, false]);
  const reader = (shown: SimulationBlock) => withReading(createElement(AuthProvider, null, createElement(ExplainerBlockView, { block: shown, reduce: true })), LOOKUP);
  expect(reader({ ...block, hidden: true, reuse: { pieceId: PIECE, storedAt: "2026-11-17T09:00:00Z" } })).toBe("");
  expect(attribute(reader(block), "explainer-block", "data-kind")).toEqual(["simulation"]);
});
