import { DEPICTED_MATERIALS } from "@/lib/depictedMaterials";
import { dictionary, integer, list, matching, nullable, object, oneOf, optional, ShapeError, text, type Shape } from "@/lib/shape";
import { UNIT_REF } from "@/lib/unitIds";

export const SVG_TAGS = [
  "svg", "g", "defs", "title", "desc", "clipPath", "mask", "marker", "pattern", "linearGradient", "stop", "filter",
  "feColorMatrix", "feComponentTransfer", "feFuncR", "feFuncG", "feFuncB", "rect", "path", "circle", "ellipse", "line",
  "polygon", "text", "tspan"
] as const;

const DOM_ID = /^[A-Za-z][\w-]*$/;
const STYLE_NAME = /^[a-z][a-z0-9-]*( [a-z][a-z0-9-]*)*$/;
const FIGURE_KEY = /^[a-z]+:[A-Za-z0-9.]+$/;
const COMPONENT_LABEL = /^[a-z0-9]+(-[a-z0-9]+)*(\/[a-z0-9]+(-[a-z0-9]+)*){2,}$/;
const COLOUR_TOKEN =
  /^--(ground|raised|sunk|rule|rule-strong|ink-[1-3]|madder|indigo|dye-[a-z]+(-[a-z]+)*|dip-[1-9]|mol-[a-z]+|atom-[a-z]+|map-[a-z]+(-[a-z]+)*|chart-[a-z]+(-[a-z]+)*)$/;
const DEPICTED_PREFIX = "--dye-";
const DEPICTED: ReadonlySet<string> = new Set(DEPICTED_MATERIALS);
const DRAWING_ATTRIBUTE = /^(?![oO][nN])[A-Za-z][A-Za-z0-9-]*$/;
const PAINT_ATTRIBUTES = new Set(["fill", "stroke", "stop-color"]);
const PAINT_VALUE = /^(none|currentColor|#(?:fff|000)|url\(#[\w-]+\)|rgba\((255,255,255|0,0,0),(0|1|0?\.\d+)\))$/;
const PAINT_TOKEN = /^var\((--[a-z0-9-]+)\)$/;
const PAINT_MIX = /^color-mix\(in srgb, var\((--[a-z0-9-]+)\) \d{1,3}%, var\((--[a-z0-9-]+)\)\)$/;
const FOREIGN_URL = /url\((?!#[\w-]+\))/;

export type SvgTag = (typeof SVG_TAGS)[number];
export type SvgNode = { tag: SvgTag; attrs?: Record<string, string>; children?: (SvgNode | string)[] };
export type Styled = { text: string; style: "i" | "b" | "sub" | "sup" };
export type Rich = (string | Styled)[];
export type TextBlock = { tag: "p" | "h2" | "h3" | "h4"; style: string | null; unit: string };
export type ComponentSlot = { component: string };
export type FigureHead = { figure: string | null; number: string; title: string; titleId: string | null; dek: string | null };
export type Species = { formula: Rich; name: string | null };
export type EquationLine = { reactants: Species[]; products: Species[] };
export type AtomRow = { element: string; left: string; right: string };
export type AtomTable = { caption: string; head: string[]; rows: AtomRow[] };
export type Equation = { label: string; style: string | null; line: EquationLine; atoms: AtomTable | null; notes: string[] };
export type Differs = { summary: string; body: string[] };
export type ColourMix = { first: string; share: number; second: string };
export type Colour = string | ColourMix;

export const unitRef = matching(UNIT_REF, "a text unit id");
export const domId = matching(DOM_ID, "an element id");
export const styleName = matching(STYLE_NAME, "a style name");
export const figureKey = matching(FIGURE_KEY, "a figure key");
export function knownColourToken(token: string): boolean {
  if (!COLOUR_TOKEN.test(token)) return false;
  return !token.startsWith(DEPICTED_PREFIX) || DEPICTED.has(token.slice(DEPICTED_PREFIX.length));
}

export const colourToken: Shape<string> = {
  expected: "a colour token",
  parse(value, path) {
    if (typeof value !== "string" || !knownColourToken(value)) throw new ShapeError(path, "a colour token");
    return value;
  }
};
export const componentLabel = matching(COMPONENT_LABEL, "a component label");
export const label = matching(/\S/, "a label");

export const positive: Shape<number> = {
  expected: "a positive whole number",
  parse(value, path) {
    const found = integer.parse(value, path);
    if (found < 1) throw new ShapeError(path, "a positive whole number");
    return found;
  }
};

export function either<A, B>(first: Shape<A>, second: Shape<B>): Shape<A | B> {
  return {
    expected: `${first.expected} or ${second.expected}`,
    parse(value, path) {
      try {
        return first.parse(value, path);
      } catch {
        return second.parse(value, path);
      }
    }
  };
}

function refusedAttribute(name: string, value: string): boolean {
  if (!DRAWING_ATTRIBUTE.test(name) || /javascript:/i.test(value) || FOREIGN_URL.test(value)) return true;
  if (!PAINT_ATTRIBUTES.has(name)) return false;
  const tokens = PAINT_TOKEN.exec(value) ?? PAINT_MIX.exec(value);
  return tokens ? !tokens.slice(1).every(knownColourToken) : !PAINT_VALUE.test(value);
}

const drawingAttributes: Shape<Record<string, string>> = {
  expected: "drawing attributes",
  parse(value, path) {
    const attrs = dictionary(/^.+$/, text).parse(value, path);
    const refused = Object.entries(attrs).find(([name, entry]) => refusedAttribute(name, entry));
    if (refused) throw new ShapeError(`${path}.${refused[0]}`, "a drawing attribute with in-drawing references and token paint");
    return attrs;
  }
};

export const svgNodeShape: Shape<SvgNode> = {
  expected: "a drawing node",
  parse: (value, path) =>
    object<SvgNode>({ tag: oneOf(SVG_TAGS), attrs: optional(drawingAttributes), children: optional(list(either(svgNodeShape, text))) }).parse(value, path)
};

export const styledShape: Shape<Styled> = object<Styled>({ text: label, style: oneOf(["i", "b", "sub", "sup"] as const) });
export const richShape: Shape<Rich> = list(either(text, styledShape), 1);
export const textBlockShape: Shape<TextBlock> = object<TextBlock>({ tag: oneOf(["p", "h2", "h3", "h4"] as const), style: nullable(styleName), unit: unitRef });
export const componentSlotShape: Shape<ComponentSlot> = object<ComponentSlot>({ component: componentLabel });
export const figureHeadShape: Shape<FigureHead> = object<FigureHead>({
  figure: nullable(figureKey),
  number: unitRef,
  title: unitRef,
  titleId: nullable(domId),
  dek: nullable(unitRef)
});
export const speciesShape: Shape<Species> = object<Species>({ formula: richShape, name: nullable(label) });
export const equationLineShape: Shape<EquationLine> = object<EquationLine>({ reactants: list(speciesShape, 1), products: list(speciesShape, 1) });
const atomTableShape: Shape<AtomTable> = object<AtomTable>({
  caption: label,
  head: list(unitRef, 4),
  rows: list(object<AtomRow>({ element: unitRef, left: unitRef, right: unitRef }), 1)
});
export const equationShape: Shape<Equation> = object<Equation>({
  label,
  style: nullable(styleName),
  line: equationLineShape,
  atoms: nullable(atomTableShape),
  notes: list(unitRef)
});
export const differsShape: Shape<Differs> = object<Differs>({ summary: label, body: list(unitRef, 1) });

const share: Shape<number> = {
  expected: "a share from 1 to 99 per cent",
  parse(value, path) {
    const found = integer.parse(value, path);
    if (found < 1 || found > 99) throw new ShapeError(path, "a share from 1 to 99 per cent");
    return found;
  }
};

export const colourShape: Shape<Colour> = either(colourToken, object<ColourMix>({ first: colourToken, share, second: colourToken }));

export const paint = (colour: Colour) =>
  typeof colour === "string" ? `var(${colour})` : `color-mix(in srgb, var(${colour.first}) ${colour.share}%, var(${colour.second}))`;
