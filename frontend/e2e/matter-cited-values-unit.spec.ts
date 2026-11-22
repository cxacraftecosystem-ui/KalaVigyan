import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";

import type { CitationLookup } from "@/components/answer/CitationContext";
import { MaterialCardView } from "@/components/answer/matter/MaterialCardView";
import { StepDetail } from "@/components/answer/matter/StepDetail";
import { itemSourceIds } from "@/lib/craftChapterReads";
import { materialCardBlockShape, reactionPlayerBlockShape, stepEnergy } from "@/lib/explainerMatter";
import type { SectionView } from "@/lib/explainerState";
import { blockSourceIds, explainerSourceNumbers } from "@/lib/explainerView";
import { parseShape, ShapeError } from "@/lib/shape";

import { attribute, withReading } from "./explainerRender";
import { FRONTEND, staticImports } from "./moduleGraph";
import { PHASE_B, phaseBBlock } from "./phaseBFixture";

const ALIZARIN_RECORD = "ffd974aa-9172-566a-8a38-dcc5c3c4f2d6";
const GI_JOURNAL = "d0f53ee9-4b97-5df7-a367-686957bdb7c8";
const MICROBES = "48309f78-3f0e-511e-a874-703135c913a6";
const DYEING = "84ad0382-a600-5df1-8b10-3220a1e6df1a";
const OXIDATION_CLAIM = "00cedcde-83f0-541b-91ab-27b13ffb72b5";
const UNCITED_CLAIM = "a claim the step does not cite";
const MINUS = "−";
const MATTER = join(FRONTEND, "components", "answer", "matter");

const player = () => phaseBBlock("reaction_player", "s4.b1");
const oxidation = () => player().steps[2];
const card = () => phaseBBlock("material_card", "s4.b2");
const alizarinCard = () => ({ ...card(), name: "Alizarin", formula: "C14H8O4", pubchemCid: 6293, sourceId: ALIZARIN_RECORD });

function lookupOf(numbered: [string, number][]): CitationLookup {
  const ids = new Set(numbered.map(([id]) => id));
  return { numbers: new Map(numbered), sourcesById: new Map(PHASE_B.sources.filter((source) => ids.has(source.id)).map((source) => [source.id, source])) };
}

function segment(html: string, from: string, to: string): string {
  const start = html.indexOf(from);
  return start < 0 ? "" : html.slice(start, html.indexOf(to, start));
}

test("a step's reaction energy is a number in kJ/mol from a claim the step cites, written with a real minus sign", () => {
  const block = player();
  const energy = { kjPerMol: -286, claimId: OXIDATION_CLAIM };
  const withEnergy = (deltaH: unknown) => ({ ...block, steps: block.steps.map((step, at) => (at === 2 ? { ...step, deltaH } : step)) });
  expect(parseShape(reactionPlayerBlockShape, withEnergy(energy)).steps[2].deltaH).toEqual(energy);
  expect(parseShape(reactionPlayerBlockShape, block).steps[2].deltaH).toBeUndefined();
  for (const wrong of [{ kjPerMol: `${MINUS}286`, claimId: OXIDATION_CLAIM }, { kjPerMol: Number.NaN, claimId: OXIDATION_CLAIM }, { kjPerMol: -286 }, { ...energy, unit: "kcal/mol" }]) {
    expect(() => parseShape(reactionPlayerBlockShape, withEnergy(wrong))).toThrow(ShapeError);
  }
  const step = oxidation();
  expect(stepEnergy({ ...step, deltaH: energy })).toEqual({ text: `ΔH = ${MINUS}286 kJ/mol`, citations: [step.citations[1]] });
  expect(stepEnergy({ ...step, deltaH: { kjPerMol: -2858.5, claimId: OXIDATION_CLAIM } })?.text).toBe(`ΔH = ${MINUS}2,858.5 kJ/mol`);
  expect(stepEnergy({ ...step, deltaH: { kjPerMol: 54, claimId: OXIDATION_CLAIM } })?.text).toBe("ΔH = +54 kJ/mol");
  expect(stepEnergy({ ...step, deltaH: { kjPerMol: -286, claimId: UNCITED_CLAIM } })).toBeNull();
  expect(stepEnergy(step)).toBeNull();
});

test("a step shows its reaction energy beside its conditions, cited by its own claim alone", () => {
  const lookup = lookupOf([
    [GI_JOURNAL, 1],
    [MICROBES, 4],
    [DYEING, 5]
  ]);
  const step = { ...oxidation(), deltaH: { kjPerMol: -286, claimId: OXIDATION_CLAIM } };
  const html = withReading(createElement(StepDetail, { step, notes: [], animate: false }), lookup);
  const row = segment(html, 'data-testid="step-energy"', "</dd>");
  expect(row).toContain(">Reaction energy</dt>");
  expect(row).toContain(`<span class="lining-nums tabular-nums">ΔH = ${MINUS}286 kJ/mol</span>`);
  expect(attribute(row, "citation-chip", "data-numbers")).toEqual(["4"]);
  const chips = attribute(html, "citation-chip", "data-numbers");
  expect(chips[chips.length - 1]).toBe("1,4,5");
  for (const quiet of [oxidation(), { ...step, deltaH: { kjPerMol: -286, claimId: UNCITED_CLAIM } }]) {
    expect(withReading(createElement(StepDetail, { step: quiet, notes: [], animate: false }), lookup)).not.toContain("Reaction energy");
  }
});

test("a material card cites its compound's PubChem record beside the formula and never links the record twice", () => {
  const block = card();
  expect(parseShape(materialCardBlockShape, alizarinCard()).sourceId).toBe(ALIZARIN_RECORD);
  expect(parseShape(materialCardBlockShape, block).sourceId).toBeUndefined();
  for (const wrong of [7, null]) expect(() => parseShape(materialCardBlockShape, { ...block, sourceId: wrong })).toThrow(ShapeError);
  const lookup = lookupOf([
    [GI_JOURNAL, 1],
    [ALIZARIN_RECORD, 2]
  ]);
  const html = withReading(createElement(MaterialCardView, { block: alizarinCard() }), lookup);
  const formula = segment(html, 'data-testid="material-formula"', 'data-testid="material-record"');
  expect(formula).toContain('aria-label="C14H8O4"');
  expect(/<a[^>]*data-testid="source-chip"[^>]*>/.exec(formula)?.[0]).toContain('href="https://pubchem.ncbi.nlm.nih.gov/compound/6293"');
  expect(formula).toContain('<span class="tabular-nums">2</span>');
  expect(segment(html, 'data-testid="material-record"', "</dd>")).toBe('data-testid="material-record">PubChem CID 6293</span>');
  expect(html.match(/pubchem\.ncbi\.nlm\.nih\.gov\/compound\/6293/g)).toHaveLength(1);

  const bare = withReading(createElement(MaterialCardView, { block: { ...alizarinCard(), formula: null } }), lookup);
  expect(bare).toContain(">Compound</dt>");
  expect(bare).not.toContain('data-testid="material-formula"');
  expect(segment(bare, 'data-testid="material-record"', "</dd>")).toContain("PubChem CID 6293");
  expect(attribute(bare, "source-chip", "href")).toEqual(["https://pubchem.ncbi.nlm.nih.gov/compound/6293"]);
});

test("a card's compound record joins the one numbering and the craft page's sources", () => {
  expect(blockSourceIds(card())).toEqual([GI_JOURNAL, GI_JOURNAL, GI_JOURNAL, GI_JOURNAL]);
  expect(blockSourceIds(alizarinCard())).toEqual([GI_JOURNAL, GI_JOURNAL, GI_JOURNAL, GI_JOURNAL, ALIZARIN_RECORD]);
  const section = { id: "s4", discipline: "CHEMISTRY", title: "Chemistry", order: 1, state: "READY", searched: null, blocks: [alizarinCard()] } as unknown as SectionView;
  expect([...explainerSourceNumbers([section])]).toEqual([
    [GI_JOURNAL, 1],
    [ALIZARIN_RECORD, 2]
  ]);
  expect(itemSourceIds({ block: alizarinCard(), part: null, figure: null, origin: null, pieceId: null })).toContain(ALIZARIN_RECORD);
});

test("the record chip has one home, shared by the molecule caption and the material card", () => {
  const homes = readdirSync(MATTER).filter((name) => /function SourceChip\b/.test(readFileSync(join(MATTER, name), "utf8")));
  expect(homes).toEqual(["SourceChip.tsx"]);
  for (const user of ["MoleculeCaption.tsx", "MaterialCardView.tsx"]) {
    expect(staticImports(readFileSync(join(MATTER, user), "utf8"))).toContain("@/components/answer/matter/SourceChip");
  }
});
