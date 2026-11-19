import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";

import { BLOCK_RENDERERS } from "@/components/answer/blockRenderers";
import type { CitationLookup } from "@/components/answer/CitationContext";
import { MaterialCardView } from "@/components/answer/matter/MaterialCardView";
import { MoleculeView } from "@/components/answer/matter/MoleculeView";
import { ReactionPlayerView } from "@/components/answer/matter/ReactionPlayer";
import { moleculeFailure } from "@/components/answer/matter/useMolecule";
import { ApiError } from "@/lib/api";
import { CONFORMER_MAX_BYTES, conformerSdf, MOLFILE_VERSIONS } from "@/lib/conformer";
import { MOLECULE_CONFORMER_PATH } from "@/lib/explainerMatter";
import type { SectionView } from "@/lib/explainerState";
import { blockCitations, blockSentences, blockSourceIds, explainerSourceNumbers } from "@/lib/explainerView";
import { materialRoleText } from "@/lib/processView";
import {
  carriedKeys,
  changeMotion,
  colourChange,
  colourChangeLine,
  DYE_FILL,
  PLAYBACK_START,
  playable,
  playbackStep,
  reactionCast,
  stepPosition,
  stepRoles,
  stepSignal,
  type Playback,
  type PlaybackAction
} from "@/lib/reactionPlayer";
import { ShapeError } from "@/lib/shape";

import { CONTENT_SECURITY_POLICY } from "../next.config";
import { attribute, FIXED_WIDE_WIDTH, gridTracks, SHRINKABLE_TRACK, withApp, withReading } from "./explainerRender";
import { eagerModules, FRONTEND, staticImports } from "./moduleGraph";
import { PHASE_B, phaseBBlock, readRepo } from "./phaseBFixture";

const player = () => phaseBBlock("reaction_player", "s4.b1");
const card = () => phaseBBlock("material_card", "s4.b2");
const molecule = () => phaseBBlock("molecule_3d", "s4.b3");
const RECORDED_SDF = readRepo("backend", "tests", "sources", "fixtures", "pubchem_conformer.sdf");
const ALIZARIN_RECORD = "ffd974aa-9172-566a-8a38-dcc5c3c4f2d6";

function played(actions: PlaybackAction[], count: number, from: Playback = PLAYBACK_START): Playback[] {
  const seen: Playback[] = [];
  actions.reduce((state, action) => {
    const next = playbackStep(state, action, count);
    seen.push(next);
    return next;
  }, from);
  return seen;
}

test("the matter kinds and the expert view have one renderer each", () => {
  for (const kind of ["reaction_player", "material_card", "molecule_3d", "expert_view"] as const) expect(BLOCK_RENDERERS[kind]).toBeDefined();
});

test("playback plays the steps in order, stops on the last, replays from the first and a chosen step pauses", () => {
  const tick = { type: "tick" } as const;
  expect(played([{ type: "play" }, tick, tick, tick, tick], 4)).toEqual([
    { at: 0, playing: true },
    { at: 1, playing: true },
    { at: 2, playing: true },
    { at: 3, playing: false },
    { at: 3, playing: false }
  ]);
  expect(played([{ type: "play" }, { type: "pause" }, tick], 4, { at: 3, playing: false })).toEqual([
    { at: 0, playing: true },
    { at: 0, playing: false },
    { at: 0, playing: false }
  ]);
  expect(played([{ type: "next" }, { type: "previous" }, { type: "previous" }, { type: "choose", index: 9 }, { type: "choose", index: -2 }], 4)).toEqual([
    { at: 1, playing: false },
    { at: 0, playing: false },
    { at: 0, playing: false },
    { at: 3, playing: false },
    { at: 0, playing: false }
  ]);
  expect(playbackStep({ at: 1, playing: true }, { type: "choose", index: 2 }, 4)).toEqual({ at: 2, playing: false });
  expect(playbackStep(PLAYBACK_START, { type: "play" }, 1)).toEqual(PLAYBACK_START);
  expect([playable(1, false), playable(4, true), playable(4, false)]).toEqual([false, false, true]);
  expect(stepPosition(2, 4)).toBe("Step 3 of 4");
});

test("the cast lists each species once in order of first appearance and a step lights its own by role", () => {
  const steps = player().steps;
  expect(reactionCast(steps).map((member) => member.key)).toEqual([
    "formula:Fe",
    "formula:CH3COOH",
    "formula:Fe(CH3COO)2",
    "formula:H2",
    "formula:C16H10N2O2",
    "formula:H^+",
    "formula:e^-",
    "formula:C16H12N2O2",
    "formula:O2",
    "formula:H2O",
    "formula:Al^3+",
    "formula:C14H8O4",
    "name:aluminium-alizarin lake"
  ]);
  expect([...stepRoles(steps[2])]).toEqual([
    ["formula:C16H12N2O2", "REACTANT"],
    ["formula:O2", "REACTANT"],
    ["formula:C16H10N2O2", "PRODUCT"],
    ["formula:H2O", "PRODUCT"]
  ]);
  expect(steps.map(stepSignal)).toEqual(["BALANCED", "BALANCED", "BALANCED", null]);
  expect(stepSignal({ balanced: false, equation: "A -> B" })).toBe("UNBALANCED");
});

test("reduced motion shows every step with its equation, species and citations, and no playback", () => {
  const html = withReading(createElement(ReactionPlayerView, { block: player(), reduce: true }));
  expect(attribute(html, "reaction-player", "data-step")).toEqual(["all"]);
  expect(attribute(html, "reaction-step", "data-open")).toEqual(["true", "true", "true", "true"]);
  expect(attribute(html, "reaction-step-detail", "data-testid")).toHaveLength(4);
  expect(html).not.toContain('data-testid="reaction-controls"');
  expect(html).not.toContain('data-testid="species-cast"');
  expect(html).toContain('aria-label="Iron + 2 Acetic acid gives Iron(II) acetate + Hydrogen"');
  expect(html).toContain("Aluminium from the alum mordant + Alizarin gives Aluminium-alizarin lake");
  const clusters = attribute(html, "citation-chip", "data-numbers").map((numbers) => numbers.split(","));
  expect(clusters.flat()).toHaveLength(11 + 2 + 2 + 12);
  expect(clusters.length).toBeLessThan(clusters.flat().length);
  expect(html.match(/>Balanced</g)).toHaveLength(3);
  for (const step of player().steps) expect(html).toContain(step.label);
});

test("playing shows the cast lit for the open step, one step open and the playback controls", () => {
  const html = withReading(createElement(ReactionPlayerView, { block: player(), reduce: false }));
  expect(attribute(html, "reaction-player", "data-step")).toEqual(["1"]);
  expect(attribute(html, "cast-species", "data-role")).toEqual(["REACTANT", "REACTANT", "PRODUCT", "PRODUCT", ...Array(9).fill("none")]);
  expect(attribute(html, "reaction-step", "data-open")).toEqual(["true", "false", "false", "false"]);
  expect(attribute(html, "reaction-step-detail", "data-testid")).toHaveLength(1);
  expect(html).toContain("Step 1 of 4");
  expect(html).toContain('data-testid="reaction-play"');
  expect(/<button[^>]*aria-label="Previous step"[^>]*>/.exec(html)?.[0]).toContain("disabled");
  expect(html).toContain('aria-current="step"');
});

test("each step shows its stage, the conditions and colours its sources state, and why it happens", () => {
  const html = withReading(createElement(ReactionPlayerView, { block: player(), reduce: true }));
  expect(attribute(html, "step-colour", "data-colour")).toEqual(["GREEN", "BLUE", "RED"]);
  expect(attribute(html, "step-colour", "data-side")).toEqual(["BEFORE", "AFTER", "AFTER"]);
  expect(attribute(html, "step-cloth", "data-testid")).toHaveLength(2);
  expect(html).toContain("At first bright green, the cloth rapidly becomes blue");
  expect(attribute(html, "step-condition", "data-testid")).toHaveLength(2);
  expect(html).toContain("Fermenting the iron paste");
  expect(html).toContain(">ten to fifteen days");
  expect(attribute(html, "step-why", "data-testid")).toHaveLength(4);
  expect(html.match(/data-testid="answer-sentence"/g)).toHaveLength(12);
  expect(html).toContain("Redox · Indigo dyeing (kun me burana)");
});

test("a stated colour is drawn as its depicted material, green turning blue oxidises from the top and other changes dip", () => {
  const [, , oxidation, lake] = player().steps;
  expect(changeMotion(colourChange(oxidation)!)).toBe("oxidise");
  expect(changeMotion(colourChange(lake)!)).toBe("dip");
  expect([DYE_FILL.BLUE, DYE_FILL.GREEN, DYE_FILL.BLACK, DYE_FILL.RED]).toEqual(["var(--dye-indigo)", "var(--dye-leuco)", "var(--dye-kut)", "var(--dye-madder-bright)"]);
  const tokens = readFileSync(join(FRONTEND, "app", "tokens.css"), "utf8");
  for (const fill of Object.values(DYE_FILL)) for (const name of fill.match(/--dye-[a-z-]+/g) ?? []) expect(tokens, name).toContain(`${name}:`);
  const html = withReading(createElement(ReactionPlayerView, { block: player(), reduce: true }));
  expect(attribute(html, "step-cloth", "data-motion")).toEqual(["oxidise", "dip"]);
  expect(html).not.toContain("opacity:0");
});

test("a colour change reads before and after, and the species one step makes for the next is the intermediate", () => {
  const [iron, reduction, oxidation, lake] = player().steps;
  expect([iron, reduction].map(colourChange)).toEqual([null, null]);
  expect(colourChangeLine(colourChange(oxidation)!)).toBe("Green turns blue");
  expect(colourChangeLine(colourChange(lake)!)).toBe("Red as it forms");
  const steps = player().steps;
  expect([0, 1, 2, 3].map((at) => [...carriedKeys(steps, at)])).toEqual([[], ["formula:C16H12N2O2"], ["formula:C16H12N2O2"], []]);
  expect(lake.stage).toBe("Red dyeing (rang) with madder or alizarin");
});

test("a material card shows its stored name, local names, role, formula, facts and handling with their citations", () => {
  const block = card();
  expect([materialRoleText("MORDANT", "MORDANT"), materialRoleText("DYE", "FIBRE"), materialRoleText(null, "MINERAL"), materialRoleText(null, null)]).toEqual([
    "Mordant",
    "Dye · Fibre",
    "Mineral",
    null
  ]);
  const html = withReading(createElement(MaterialCardView, { block }));
  expect(html).toContain("Alum (fatakdi)");
  expect(html).toContain("fatakdi · fitkari · karam");
  expect(html).toContain(">Mordant<");
  expect(html).toContain('aria-label="KAl(SO4)2·12H2O"');
  expect(html).not.toContain("pubchem.ncbi.nlm.nih.gov");
  for (const sentence of [...block.facts, ...block.handling]) expect(html).toContain(sentence.text);
  expect(html).toContain('data-testid="material-handling"');
  expect(html.match(/data-testid="citation-chip"/g)).toHaveLength(3);

  const linked = withReading(createElement(MaterialCardView, { block: { ...block, pubchemCid: 22121, wikidataId: "Q131276", handling: [] } }));
  expect(linked).toContain('href="https://pubchem.ncbi.nlm.nih.gov/compound/22121"');
  expect(linked).toContain('href="https://www.wikidata.org/wiki/Q131276"');
  expect(linked).not.toContain('data-testid="material-handling"');
});

test("the client checks a conformer as the PubChem adapter does, and asks the backend's route", () => {
  expect(conformerSdf(RECORDED_SDF, 6293)).toBe(RECORDED_SDF);
  const lines = RECORDED_SDF.split("\n");
  const flat = [lines[0], `${lines[1].slice(0, 20)}2D${lines[1].slice(22)}`, ...lines.slice(2)].join("\n");
  for (const [value, cid] of [
    [RECORDED_SDF, 6294],
    [flat, 6293],
    [RECORDED_SDF.replace("V2000", "V9999"), 6293],
    [RECORDED_SDF.replace("$$$$", ""), 6293],
    [RECORDED_SDF.replace("OEChem", "OEChém"), 6293],
    [`${RECORDED_SDF}${" ".repeat(CONFORMER_MAX_BYTES)}`, 6293],
    [null, 6293]
  ] as const) {
    expect(() => conformerSdf(value, cid)).toThrow(ShapeError);
  }
  const pubchem = readRepo("backend", "app", "sources", "reference", "pubchem.py");
  const [, kib, unit] = /^CONFORMER_MAX_BYTES = (\d+) \* (\d+)$/m.exec(pubchem) ?? [];
  expect(CONFORMER_MAX_BYTES).toBe(Number(kib) * Number(unit));
  expect([...MOLFILE_VERSIONS]).toEqual([.../^MOLFILE_VERSIONS = \(([^)]+)\)$/m.exec(pubchem)![1].matchAll(/"([^"]+)"/g)].map((found) => found[1]));
  const route = readRepo("backend", "app", "api", "routes", "molecules.py");
  const prefix = /APIRouter\(prefix="([^"]+)"/.exec(route)?.[1];
  const path = /@router\.get\("([^"]+)"\)\nasync def conformer/.exec(route)?.[1];
  expect(MOLECULE_CONFORMER_PATH(6293)).toBe(`${prefix}${path?.replace("{pubchem_cid}", "6293")}`);
});

test("a molecule waits for its view, names its compound and cites its PubChem record; a missing conformer hides it", () => {
  const source = PHASE_B.sources.find((entry) => entry.id === ALIZARIN_RECORD);
  const lookup: CitationLookup = { numbers: new Map([[ALIZARIN_RECORD, 7]]), sourcesById: new Map(source ? [[source.id, source]] : []), onOpen: () => undefined };
  const html = withApp(createElement(MoleculeView, { block: molecule() }), lookup);
  expect(attribute(html, "molecule-3d", "data-status")).toEqual(["waiting"]);
  expect(html).toContain('aria-label="Loading 3D view"');
  expect(html).not.toContain('data-testid="molecule-tools"');
  expect(html).toContain(">Alizarin<");
  expect(html).toContain('aria-label="C14H8O4"');
  expect(html).toContain("PubChem CID 6293");
  expect(/<a[^>]*data-testid="source-chip"[^>]*>/.exec(html)?.[0]).toContain('href="https://pubchem.ncbi.nlm.nih.gov/compound/6293"');
  expect(html).toContain('<span class="tabular-nums">7</span>');
  expect(moleculeFailure(new ApiError(404, "Not Found", null))).toBe("hidden");
  expect(moleculeFailure(new ShapeError("conformer", "an SDF record"))).toBe("hidden");
  expect(moleculeFailure(new ApiError(503, "Unavailable", null))).toBe("failed");
  expect(moleculeFailure(new TypeError("Failed to fetch"))).toBe("failed");
});

test("the matter blocks join the answer's one numbering: reactions by their citations, the molecule by its record", () => {
  const blocks = [player(), card(), molecule()];
  expect(blockSentences(player()).map((sentence) => sentence.id)).toEqual(Array.from({ length: 12 }, (_, n) => `s4.b1.${n + 1}`));
  expect(blockSentences(card()).map((sentence) => sentence.id)).toEqual(["s4.b2.1", "s4.b2.2", "s4.b2.3"]);
  expect(blockCitations(player())).toHaveLength(13 + 2 + 3 + 12);
  expect(blockSourceIds(molecule())).toEqual([ALIZARIN_RECORD]);
  const section = { id: "s4", discipline: "CHEMISTRY", title: "Chemistry", order: 1, state: "READY", searched: null, blocks } as unknown as SectionView;
  expect([...explainerSourceNumbers([section])]).toEqual([
    ["4ce205e3-653f-51db-9e49-14fb3b3f2e14", 1],
    ["d0f53ee9-4b97-5df7-a367-686957bdb7c8", 2],
    ["8a32aea5-44f7-5a50-942b-97534f0e5d8e", 3],
    ["48309f78-3f0e-511e-a874-703135c913a6", 4],
    ["84ad0382-a600-5df1-8b10-3220a1e6df1a", 5],
    ["9187df8b-62e3-510a-ba5d-827ec098c84c", 6],
    [ALIZARIN_RECORD, 7]
  ]);
});

function sourceFiles(folder: string): string[] {
  return readdirSync(folder).flatMap((name) => {
    const path = join(folder, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.tsx?$/.test(name) ? [path] : [];
  });
}

test("3Dmol.js is pinned, reached only through its adapter, loaded on demand and needs nothing new from the CSP", () => {
  const manifest = JSON.parse(readFileSync(join(FRONTEND, "package.json"), "utf8")) as { dependencies: Record<string, string> };
  expect(manifest.dependencies["3dmol"]).toMatch(/^\d+\.\d+\.\d+$/);
  const users = ["app", "components", "lib"].flatMap((folder) => sourceFiles(join(FRONTEND, folder))).filter((file) => readFileSync(file, "utf8").includes('"3dmol"'));
  expect(users.map((file) => file.slice(FRONTEND.length + 1).replace(/\\/g, "/"))).toEqual(["lib/moleculeViewer.ts"]);
  const adapter = readFileSync(join(FRONTEND, "lib", "moleculeViewer.ts"), "utf8");
  expect(staticImports(adapter)).not.toContain("3dmol");
  expect(adapter.match(/import\("3dmol"\)/g)).toHaveLength(1);
  for (const file of eagerModules("@/components/answer/blockRenderers")) {
    expect(staticImports(readFileSync(join(FRONTEND, file), "utf8")), file).not.toContain("3dmol");
  }
  expect(CONTENT_SECURITY_POLICY).not.toContain("unsafe-eval");
  expect(CONTENT_SECURITY_POLICY).not.toMatch(/pubchem|3dmol/i);
});

test("matter renderers lay out in shrinkable columns so nothing widens a phone page", () => {
  const html = [
    withReading(createElement(ReactionPlayerView, { block: player(), reduce: false })),
    withReading(createElement(ReactionPlayerView, { block: player(), reduce: true })),
    withReading(createElement(MaterialCardView, { block: card() })),
    withApp(createElement(MoleculeView, { block: molecule() }))
  ].join("");
  const tracks = gridTracks(html);
  expect(tracks.length).toBeGreaterThan(0);
  for (const track of tracks) expect(track).toMatch(SHRINKABLE_TRACK);
  expect(html).not.toMatch(FIXED_WIDE_WIDTH);
  expect(html.match(/class="[^"]*\bmin-w-0\b/g)?.length ?? 0).toBeGreaterThan(5);
});
