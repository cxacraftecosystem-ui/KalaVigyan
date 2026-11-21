import {
  colourShape,
  colourToken,
  differsShape,
  domId,
  either,
  equationShape,
  figureHeadShape,
  label,
  positive,
  richShape,
  styledShape,
  svgNodeShape,
  unitRef,
  type Colour,
  type Differs,
  type Equation,
  type FigureHead,
  type Rich,
  type Styled,
  type SvgNode
} from "@/lib/componentSpecsScienceParts";
import { boolean, list, matching, nullable, object, oneOf, optional, ShapeError, tagged, text, type Shape } from "@/lib/shape";

export const SWATCH_MARKS = ["clear", "gas", "ion"] as const;
export const PHASE_KEY = /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/;

export type Condition = { term: string; value: string };
export type StepText = {
  kicker: string;
  heading: string;
  paragraphs: string[];
  bond: string | null;
  link: string | null;
  conditions: Condition[];
  differs: Differs | null;
};
export type LaneSpecies = {
  item: "species";
  swatch: Colour | (typeof SWATCH_MARKS)[number];
  name: Rich;
  formula: Rich | null;
  state: (string | Styled)[];
  cid: number | null;
};
export type LaneItem = LaneSpecies | { item: "plus" } | { item: "arrow"; label: string };
export type ChemistryPart =
  | { part: "lane"; label: string; items: LaneItem[] }
  | { part: "equation"; equation: Equation }
  | { part: "none"; unit: string };
export type StepScene = { whereIcon: SvgNode; where: string; art: SvgNode[] };
export type ReactionStep = { name: string; text: StepText; chemistry: { parts: ChemistryPart[] }; scene: StepScene | null };
export type ReactionPlayerSpec = {
  id: string;
  track: string;
  head: FigureHead;
  current: number;
  steps: ReactionStep[];
  scenes: SvgNode[];
  key: string | null;
  status: string;
};
export type DipPhase = { pose: string; drawing: SvgNode; kicker: string; text: string };
export type DipPlayerSpec = {
  id: string;
  head: FigureHead;
  phase: string;
  scene: SvgNode;
  stripLabel: string;
  phases: DipPhase[];
  dipAgain: string;
  status: string;
  dipsLabel: string;
  dips: string[];
  equation?: Equation;
};
export type StageEntry = {
  name: string;
  english: string;
  local: boolean;
  after: string;
  number: string;
  heading: string;
  texts: string[];
  why: string | null;
  differs: Differs | null;
  afterSentence: string | null;
  materials: string | null;
  swatch?: string;
};
export type StagePlayerSpec = {
  key: string;
  head: FigureHead;
  drawing: SvgNode;
  restName: string;
  play: string;
  source: string;
  stages: StageEntry[];
  finish: { heading: string; paragraphs: string[] };
  afterLabel?: string;
};

const stepTextShape: Shape<StepText> = object<StepText>({
  kicker: unitRef,
  heading: unitRef,
  paragraphs: list(unitRef, 1),
  bond: nullable(label),
  link: nullable(unitRef),
  conditions: list(object<Condition>({ term: unitRef, value: unitRef })),
  differs: nullable(differsShape)
});

const laneItemShape: Shape<LaneItem> = tagged<LaneItem>("item", {
  species: object<LaneSpecies>({
    item: oneOf(["species"] as const),
    swatch: either(colourShape, oneOf(SWATCH_MARKS)),
    name: richShape,
    formula: nullable(richShape),
    state: list(either(text, styledShape)),
    cid: nullable(positive)
  }),
  plus: object<{ item: "plus" }>({ item: oneOf(["plus"] as const) }),
  arrow: object<{ item: "arrow"; label: string }>({ item: oneOf(["arrow"] as const), label })
});

const chemistryPartShape: Shape<ChemistryPart> = tagged<ChemistryPart>("part", {
  lane: object<{ part: "lane"; label: string; items: LaneItem[] }>({ part: oneOf(["lane"] as const), label, items: list(laneItemShape, 1) }),
  equation: object<{ part: "equation"; equation: Equation }>({ part: oneOf(["equation"] as const), equation: equationShape }),
  none: object<{ part: "none"; unit: string }>({ part: oneOf(["none"] as const), unit: unitRef })
});

const stepShape: Shape<ReactionStep> = object<ReactionStep>({
  name: label,
  text: stepTextShape,
  chemistry: object<{ parts: ChemistryPart[] }>({ parts: list(chemistryPartShape, 2) }),
  scene: nullable(object<StepScene>({ whereIcon: svgNodeShape, where: unitRef, art: list(svgNodeShape, 1) }))
});

export const reactionPlayerShape: Shape<ReactionPlayerSpec> = {
  expected: "a reaction player resting on one of its steps",
  parse(value, path) {
    const player = object<ReactionPlayerSpec>({
      id: domId,
      track: label,
      head: figureHeadShape,
      current: positive,
      steps: list(stepShape, 2),
      scenes: list(svgNodeShape),
      key: nullable(label),
      status: unitRef
    }).parse(value, path);
    if (player.current > player.steps.length) throw new ShapeError(`${path}.current`, "a step the player has");
    return player;
  }
};

export const dipPlayerShape: Shape<DipPlayerSpec> = object<DipPlayerSpec>({
  id: domId,
  head: figureHeadShape,
  phase: unitRef,
  scene: svgNodeShape,
  stripLabel: label,
  phases: list(object<DipPhase>({ pose: matching(PHASE_KEY, "a phase key"), drawing: svgNodeShape, kicker: unitRef, text: unitRef }), 2),
  dipAgain: label,
  status: unitRef,
  dipsLabel: unitRef,
  dips: list(colourToken, 1),
  equation: optional(equationShape)
});

export const stagePlayerShape: Shape<StagePlayerSpec> = object<StagePlayerSpec>({
  key: domId,
  head: figureHeadShape,
  drawing: svgNodeShape,
  restName: unitRef,
  play: label,
  source: unitRef,
  stages: list(
    object<StageEntry>({
      name: label,
      english: label,
      local: boolean,
      after: label,
      number: unitRef,
      heading: unitRef,
      texts: list(unitRef, 1),
      why: nullable(unitRef),
      differs: nullable(differsShape),
      afterSentence: nullable(unitRef),
      materials: nullable(unitRef),
      swatch: optional(colourToken)
    }),
    2
  ),
  finish: object<{ heading: string; paragraphs: string[] }>({ heading: unitRef, paragraphs: list(unitRef, 1) }),
  afterLabel: optional(label)
});
