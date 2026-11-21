import {
  colourToken,
  domId,
  either,
  equationLineShape,
  figureHeadShape,
  figureKey,
  label,
  positive,
  richShape,
  speciesShape,
  styleName,
  svgNodeShape,
  textBlockShape,
  unitRef,
  type EquationLine,
  type FigureHead,
  type Rich,
  type Species,
  type SvgNode,
  type TextBlock
} from "@/lib/componentSpecsScienceParts";
import { heldTextShape, type HeldMark } from "@/lib/componentSpecsPlates";
import { list, nullable, number, object, oneOf, optional, ShapeError, tagged, type Shape } from "@/lib/shape";

const CITE_MARK = "cite";

export const citeMarkShape: Shape<HeldMark> = {
  expected: "a citation",
  parse(value, path) {
    const [mark] = heldTextShape.parse([value], path);
    if (typeof mark === "string" || mark.m !== CITE_MARK) throw new ShapeError(path, "a citation");
    return mark;
  }
};

export type EquationCardSpec = { kicker: string; title: string; mark: string; line: EquationLine; why: string };
export type ChainText = { part: "text"; text: TextBlock };
export type ChainStep = { part: "step"; player: string; step: number; figure: string; figureLabel: string };
export type ChainDrawing = { part: "drawing"; drawing: SvgNode };
export type ChainEquation = {
  part: "equation";
  style: string;
  label: string;
  lineLabel: string;
  reactants: Species[];
  products: Species[];
  count: string;
};
export type ChainPart = ChainText | ChainStep | ChainDrawing | ChainEquation;
export type ChainLink = { style: string | null; kicker: string; parts: ChainPart[] };
export type Chain = { headingId: string; heading: string; links: ChainLink[] };
export type DiagramSpec = { drawing: SvgNode | null; chain: Chain | null };
export type StructureMolecule = {
  drawing: SvgNode;
  name: string;
  formula: Rich;
  note: string;
  atomsTerm: string;
  atoms: string;
  recordTerm: string;
  cid: number;
  recordCite?: HeldMark | null;
};
export type KeySwatch = { colour: string; label: string };
export type StructureDiagramSpec = {
  id: string;
  head: FigureHead;
  dekStyle: string | null;
  scale: string;
  molecules: StructureMolecule[];
  notes: TextBlock[];
  key: string;
  swatches: KeySwatch[];
  swatchNote: TextBlock | null;
};
export type MoleculeModel = {
  key: string;
  cid: number;
  yaw: number;
  pitch: number;
  name: string;
  dialLabel: string;
  formula: Rich;
  atoms: string;
  note: string;
  drawing: SvgNode;
};
export type AtomKeyItem = { swatch: string | null; label: string };
export type Molecule3dSpec = { head: FigureHead; molecules: MoleculeModel[]; side: TextBlock[]; key: AtomKeyItem[] };

export const equationCardShape: Shape<EquationCardSpec> = object<EquationCardSpec>({
  kicker: unitRef,
  title: unitRef,
  mark: unitRef,
  line: equationLineShape,
  why: unitRef
});

const chainPartShape: Shape<ChainPart> = tagged<ChainPart>("part", {
  text: object<ChainText>({ part: oneOf(["text"] as const), text: textBlockShape }),
  step: object<ChainStep>({ part: oneOf(["step"] as const), player: domId, step: positive, figure: figureKey, figureLabel: label }),
  drawing: object<ChainDrawing>({ part: oneOf(["drawing"] as const), drawing: svgNodeShape }),
  equation: object<ChainEquation>({
    part: oneOf(["equation"] as const),
    style: styleName,
    label: unitRef,
    lineLabel: label,
    reactants: list(speciesShape, 1),
    products: list(speciesShape, 1),
    count: label
  })
});

const chainShape: Shape<Chain> = object<Chain>({
  headingId: domId,
  heading: unitRef,
  links: list(object<ChainLink>({ style: nullable(styleName), kicker: unitRef, parts: list(chainPartShape, 1) }), 2)
});

export const diagramShape: Shape<DiagramSpec> = {
  expected: "a diagram: one drawing or one chain",
  parse(value, path) {
    const spec = object<DiagramSpec>({ drawing: nullable(svgNodeShape), chain: nullable(chainShape) }).parse(value, path);
    if ((spec.drawing === null) === (spec.chain === null)) throw new ShapeError(path, "one drawing or one chain");
    return spec;
  }
};

export const structureDiagramShape: Shape<StructureDiagramSpec> = object<StructureDiagramSpec>({
  id: domId,
  head: figureHeadShape,
  dekStyle: nullable(styleName),
  scale: unitRef,
  molecules: list(
    object<StructureMolecule>({
      drawing: svgNodeShape,
      name: label,
      formula: richShape,
      note: label,
      atomsTerm: unitRef,
      atoms: unitRef,
      recordTerm: unitRef,
      cid: positive,
      recordCite: optional(nullable(citeMarkShape))
    }),
    1
  ),
  notes: list(textBlockShape),
  key: label,
  swatches: list(object<KeySwatch>({ colour: colourToken, label })),
  swatchNote: nullable(textBlockShape)
});

export const molecule3dShape: Shape<Molecule3dSpec> = object<Molecule3dSpec>({
  head: figureHeadShape,
  molecules: list(
    object<MoleculeModel>({
      key: domId,
      cid: positive,
      yaw: number,
      pitch: number,
      name: label,
      dialLabel: label,
      formula: richShape,
      atoms: label,
      note: label,
      drawing: svgNodeShape
    }),
    1
  ),
  side: list(textBlockShape),
  key: list(object<AtomKeyItem>({ swatch: nullable(either(colourToken, oneOf(["ring"] as const))), label }), 1)
});
