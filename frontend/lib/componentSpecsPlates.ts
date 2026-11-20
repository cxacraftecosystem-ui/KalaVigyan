import type { MonographMark, MonographNode } from "@/lib/monographDocument";
import { boolean, integer, list, matching, nullable, number, object, oneOf, optional, ShapeError, text, type Shape } from "@/lib/shape";

export const DYE_NAMES = ["cloth", "harda", "harda-dry", "lime", "lime-edge", "kut", "kesari", "mud", "mud-wet", "leuco", "vat-liquor", "indigo", "indigo-deep", "madder", "madder-bright", "pink", "pink-edge"] as const;
export const DRAWING_TAGS = ["svg", "g", "defs", "title", "desc", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text", "tspan", "use", "linearGradient", "radialGradient", "stop", "pattern", "mask", "clipPath", "filter", "feGaussianBlur"] as const;
export const PLATE_SETTINGS = ["figure", "row", "pull", "opener", "masthead"] as const;
export const VOICE_SETTINGS = ["testimony", "coda"] as const;
export const GRADES = ["A", "B", "C", "D"] as const;

const ITALIC_ROLES = ["loc", "bot", "ring", "on"];
const MARK_FIELDS: Readonly<Record<string, readonly string[]>> = {
  s: ["cls", "src", "sid", "pair"],
  span: ["cls"],
  cite: ["key", "g", "shown"],
  i: ["role"],
  link: ["cls", "href", "rel", "target", "ask", "lang"],
  figref: ["ref"],
  b: [],
  sub: [],
  sup: [],
  mark: []
};
const DRAWING_ATTRIBUTE = /^[A-Za-z][A-Za-z0-9:_-]*$/;
const REFERENCE_ATTRIBUTES = ["href", "xlink:href"];

export type DyeName = (typeof DYE_NAMES)[number];
export type DrawingTag = (typeof DRAWING_TAGS)[number];
export type DrawingElement = { tag: DrawingTag; attrs: Record<string, string>; children: (DrawingElement | string)[] };
export type ShownSource = { number: number; title: string };
export type HeldMark = MonographMark;
export type HeldNode = MonographNode;
export type PictureFocal = { x: number; y: number; width: number; height: number };
export type Picture = { src: string; width: number; height: number; alt: string; loading: "eager" | "lazy" | null; fetchPriority: "high" | null; decoding: "sync" | "async" | null; focal?: PictureFocal };
export type ArtFrame = { symbol: string; viewBox: string; width: number; height: number };

export const unitRef = matching(/^u\d{4}$/, "a unit id");
export const componentLabel = matching(/^[a-z0-9]+(-[a-z0-9]+)*(\/[a-z0-9]+(-[a-z0-9]+)*){2,}$/, "a component label");
export const className = matching(/^[A-Za-z][A-Za-z0-9_-]*$/, "a class name");
export const domId = matching(/^[A-Za-z][A-Za-z0-9_:.-]*$/, "an element id");
export const viewBox = matching(/^-?\d+(\.\d+)? -?\d+(\.\d+)? \d+(\.\d+)? \d+(\.\d+)?$/, "a view box");
export const fileName = matching(/^[a-z0-9]+(-[a-z0-9]+)*$/, "a file name");
export const calendarDay = matching(/^\d{4}-\d{2}-\d{2}$/, "a calendar day");
export const dyeName = oneOf(DYE_NAMES);
const fraction: Shape<number> = {
  expected: "a fraction from 0 to 1",
  parse(value, path) {
    const found = number.parse(value, path);
    if (found < 0 || found > 1) throw new ShapeError(path, "a fraction from 0 to 1");
    return found;
  }
};
export const pictureShape = object<Picture>({
  src: matching(/^(\/monographs\/[a-z0-9-]+\/img\/[A-Za-z0-9._-]+\.(jpg|jpeg|png|webp)|\/api\/(crafts\/contributed|knowledge\/pages\/pictures)\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|https:\/\/upload\.wikimedia\.org\/wikipedia\/commons\/[0-9a-f]\/[0-9a-f]{2}\/[^\s/?#]+)$/, "a monograph, contributed or Wikimedia Commons picture"),
  width: integer,
  height: integer,
  alt: text,
  loading: nullable(oneOf(["eager", "lazy"] as const)),
  fetchPriority: nullable(oneOf(["high"] as const)),
  decoding: nullable(oneOf(["sync", "async"] as const)),
  focal: optional(object<PictureFocal>({ x: fraction, y: fraction, width: fraction, height: fraction }))
});
export const artFrameShape = object<ArtFrame>({ symbol: domId, viewBox, width: integer, height: integer });

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function drawingAttributes(value: unknown, path: string): Record<string, string> {
  if (!isRecord(value)) throw new ShapeError(path, "an object of attributes");
  for (const [name, entry] of Object.entries(value)) {
    if (!DRAWING_ATTRIBUTE.test(name) || name.toLowerCase().startsWith("on")) throw new ShapeError(`${path}.${name}`, "a drawing attribute");
    if (typeof entry !== "string") throw new ShapeError(`${path}.${name}`, "text");
    if (REFERENCE_ATTRIBUTES.includes(name) && !entry.startsWith("#")) throw new ShapeError(`${path}.${name}`, "a reference within the page");
    if (entry.replace(/\s/g, "").toLowerCase().includes("javascript:")) throw new ShapeError(`${path}.${name}`, "a value that runs no script");
  }
  return value as Record<string, string>;
}

export const drawingShape: Shape<DrawingElement> = {
  expected: "a drawing element",
  parse(value, path) {
    if (!isRecord(value)) throw new ShapeError(path, "a drawing element");
    const unknown = Object.keys(value).filter((name) => !["tag", "attrs", "children"].includes(name));
    if (unknown.length) throw new ShapeError(`${path}.${unknown[0]}`, "no such field");
    const tag = oneOf(DRAWING_TAGS).parse(value.tag, `${path}.tag`);
    const attrs = drawingAttributes(value.attrs ?? {}, `${path}.attrs`);
    const children = value.children ?? [];
    if (!Array.isArray(children)) throw new ShapeError(`${path}.children`, "a list");
    return { tag, attrs, children: children.map((child, index) => (typeof child === "string" ? child : drawingShape.parse(child, `${path}.children[${index}]`))) };
  }
};

function checkCite(mark: Record<string, unknown>, path: string): void {
  const keys = mark.g;
  if (typeof mark.key !== "string" || !mark.key || !Array.isArray(keys) || keys.length === 0 || !keys.every((key) => typeof key === "string")) throw new ShapeError(path, "a citation with its key and sources");
  const shown = list(object<ShownSource>({ number: integer, title: text }), 1).parse(mark.shown, `${path}.shown`);
  const numbers = shown.map((entry) => entry.number);
  const ordered = [...new Set(numbers)].sort((a, b) => a - b);
  if (numbers.some((number) => number < 1) || numbers.join(",") !== ordered.join(",")) throw new ShapeError(`${path}.shown`, "each source number once, in order");
}

function checkMark(mark: Record<string, unknown>, path: string): void {
  const name = mark.m;
  const fields = typeof name === "string" ? MARK_FIELDS[name] : undefined;
  if (!fields) throw new ShapeError(`${path}.m`, "an inline mark");
  const extra = Object.keys(mark).filter((key) => key !== "m" && key !== "c" && !fields.includes(key));
  if (extra.length) throw new ShapeError(`${path}.${extra[0]}`, "no such field");
  if (name === "cite") checkCite(mark, path);
  if (name === "link" && typeof mark.href !== "string") throw new ShapeError(`${path}.href`, "a link target");
  if (name === "i" && mark.role !== undefined && !ITALIC_ROLES.includes(String(mark.role))) throw new ShapeError(`${path}.role`, "an italic role");
  if (name === "figref" && typeof mark.ref !== "string") throw new ShapeError(`${path}.ref`, "a figure reference");
}

function heldNodes(value: unknown, path: string): HeldNode[] {
  if (!Array.isArray(value)) throw new ShapeError(path, "a list of text and marks");
  return value.map((node, index) => {
    const at = `${path}[${index}]`;
    if (typeof node === "string") return node;
    if (!isRecord(node)) throw new ShapeError(at, "text or a mark");
    checkMark(node, at);
    if (node.c !== undefined) heldNodes(node.c, `${at}.c`);
    return node as HeldMark;
  });
}

export const heldTextShape: Shape<HeldNode[]> = {
  expected: "held text",
  parse(value, path) {
    const nodes = heldNodes(value, path);
    if (nodes.length === 0) throw new ShapeError(path, "at least one node of held text");
    return nodes;
  }
};

export type HeldOrUnit = string | HeldNode[];

export const heldOrUnitShape: Shape<HeldOrUnit> = {
  expected: "a unit id or held text",
  parse(value, path) {
    return typeof value === "string" ? unitRef.parse(value, path) : heldTextShape.parse(value, path);
  }
};

export type CaptionLine = { unit: string; look: boolean };
export type PlateFigure = { classes: string[]; crop: string | null; captions: CaptionLine[]; credit: string };
export type PlateRow = { classes: string[]; note: string };
export type PlatePull = { classes: string[]; box: string; quote: string; attribution: HeldOrUnit };
export type ChapterOpener = { chapterNo: string; kicker: string; title: string; titleId: string; dek: string; credit: string };
export type GradeCount = { grade: (typeof GRADES)[number]; count: number };
export type MastheadLabel = { kicker: string; title: string; seal: DrawingElement; registration: HeldOrUnit; place: string; sources: number; grades: GradeCount[]; curated: string };
export type PicturePlateSpec = {
  setting: (typeof PLATE_SETTINGS)[number];
  picture: Picture;
  figure: PlateFigure | null;
  row: PlateRow | null;
  pull: PlatePull | null;
  opener: ChapterOpener | null;
  masthead: MastheadLabel | null;
};

const plateFigureShape = object<PlateFigure>({
  classes: list(className),
  crop: nullable(className),
  captions: list(object<CaptionLine>({ unit: unitRef, look: boolean }), 1),
  credit: unitRef
});
const mastheadShape = object<MastheadLabel>({
  kicker: unitRef,
  title: unitRef,
  seal: drawingShape,
  registration: heldOrUnitShape,
  place: text,
  sources: integer,
  grades: list(object<GradeCount>({ grade: oneOf(GRADES), count: integer }), 1),
  curated: calendarDay
});

export const picturePlateShape = object<PicturePlateSpec>({
  setting: oneOf(PLATE_SETTINGS),
  picture: pictureShape,
  figure: nullable(plateFigureShape),
  row: nullable(object<PlateRow>({ classes: list(className, 1), note: unitRef })),
  pull: nullable(object<PlatePull>({ classes: list(className, 1), box: className, quote: unitRef, attribution: heldOrUnitShape })),
  opener: nullable(object<ChapterOpener>({ chapterNo: unitRef, kicker: unitRef, title: unitRef, titleId: domId, dek: unitRef, credit: unitRef })),
  masthead: nullable(mastheadShape)
});

export type SpecimenPlateSpec = {
  picture: Picture;
  phase: string;
  kicker: string;
  name: string;
  nameId: string;
  sentence: string;
  replay: { label: string; statusId: string; status: string };
  credit: string;
};
export const specimenPlateShape = object<SpecimenPlateSpec>({
  picture: pictureShape,
  phase: className,
  kicker: unitRef,
  name: unitRef,
  nameId: domId,
  sentence: unitRef,
  replay: object<SpecimenPlateSpec["replay"]>({ label: text, statusId: domId, status: unitRef }),
  credit: unitRef
});

export type LabelFact = { term: string; value: string };
export type LabelCardSpec = { variant: string; kicker: string; seal: DrawingElement; sentence: string; inset: string | null; facts: LabelFact[] };
export const labelCardShape = object<LabelCardSpec>({
  variant: className,
  kicker: unitRef,
  seal: drawingShape,
  sentence: unitRef,
  inset: nullable(componentLabel),
  facts: list(object<LabelFact>({ term: unitRef, value: unitRef }), 1)
});

export type Swatch = { dye: DyeName; caption: string };
export type ColourCard = { before: Swatch; join: "becomes" | "or"; after: Swatch; name: string; agent: string; text: string };
export type SwatchCardsSpec = { chapterNo: string; title: string; titleId: string; intro: string; weave: string; colours: ColourCard[] };
const swatchShape = object<Swatch>({ dye: dyeName, caption: unitRef });
export const swatchCardsShape = object<SwatchCardsSpec>({
  chapterNo: unitRef,
  title: unitRef,
  titleId: domId,
  intro: unitRef,
  weave: domId,
  colours: list(object<ColourCard>({ before: swatchShape, join: oneOf(["becomes", "or"] as const), after: swatchShape, name: unitRef, agent: unitRef, text: unitRef }), 1)
});

export type PairSwatch = { ground: DyeName; motif: DrawingElement[]; label: string };
export type StageLink = { stage: number; label: HeldNode[] };
export type SwatchPairSpec = {
  id: string;
  wide: boolean;
  pairClass: string;
  description: string;
  weave: string;
  swatches: PairSwatch[];
  when: string;
  title: string;
  texts: string[];
  go: StageLink | null;
};
export const swatchPairShape = object<SwatchPairSpec>({
  id: domId,
  wide: boolean,
  pairClass: className,
  description: text,
  weave: domId,
  swatches: list(object<PairSwatch>({ ground: dyeName, motif: list(drawingShape, 1), label: text }), 2),
  when: unitRef,
  title: unitRef,
  texts: list(unitRef, 1),
  go: nullable(object<StageLink>({ stage: integer, label: heldTextShape }))
});

export type CreditLine = { unit: string | null; text: HeldNode[] | null };
export type CreditGroup = { title: string; listClass: string | null; lines: CreditLine[] };
export type CreditsSpec = { groups: CreditGroup[] };
export const creditsShape = object<CreditsSpec>({
  groups: list(object<CreditGroup>({ title: unitRef, listClass: nullable(className), lines: list(object<CreditLine>({ unit: nullable(unitRef), text: nullable(heldTextShape) }), 1) }), 1)
});

export type AiIllustrationSpec = { section: number; art: ArtFrame; subject: string; sentences: number[]; made: string; downloadName: string };
export const aiIllustrationShape = object<AiIllustrationSpec>({
  section: integer,
  art: artFrameShape,
  subject: text,
  sentences: list(integer, 1),
  made: calendarDay,
  downloadName: fileName
});

export type Playback = { durationMs: number; stepMs: number; restMs: number };
const playbackShape = object<Playback>({ durationMs: integer, stepMs: integer, restMs: integer });

export type AiVideoSpec = { section: number; art: DrawingElement; phase: string; playback: Playback; caption: HeldNode[]; made: string; downloadKey: string; downloadName: string };
export const aiVideoShape = object<AiVideoSpec>({
  section: integer,
  art: drawingShape,
  phase: unitRef,
  playback: playbackShape,
  caption: heldTextShape,
  made: calendarDay,
  downloadKey: text,
  downloadName: fileName
});

export type FilmScene = { art: ArtFrame; title: string; field: string; forming: boolean };
export type FilmSpec = {
  title: string;
  meta: string;
  sceneLabel: string;
  subtitle: string;
  scenes: FilmScene[];
  playback: Playback;
  tags: string[];
  note: string;
  downloadName: string;
  subtitlesName: string;
};
export const filmShape = object<FilmSpec>({
  title: unitRef,
  meta: unitRef,
  sceneLabel: unitRef,
  subtitle: unitRef,
  scenes: list(object<FilmScene>({ art: artFrameShape, title: text, field: text, forming: boolean }), 1),
  playback: playbackShape,
  tags: list(text, 1),
  note: text,
  downloadName: fileName,
  subtitlesName: fileName
});

export type ComicPanel = { layout: string | null; caption: HeldOrUnit; art: DrawingElement; tag: string };
export type ComicSpec = { label: string; panels: ComicPanel[] };
export const comicShape = object<ComicSpec>({
  label: text,
  panels: list(object<ComicPanel>({ layout: nullable(className), caption: heldOrUnitShape, art: drawingShape, tag: text }), 1)
});

export type AudioPlayerSpec = { title: string; description: string; action: string; minutes: number; playerId: string };
export const audioPlayerShape = object<AudioPlayerSpec>({ title: unitRef, description: unitRef, action: text, minutes: integer, playerId: domId });

export type VoiceEcho = { quote: string; attribution: HeldOrUnit };
export type VoiceTestimony = { kicker: string; kickerId: string; evidence: string; quote: string; credit: string; meta: string; echo: VoiceEcho | null };
export type VoiceCoda = { label: string; viewBox: string; tile: string; weave: string; kicker: string; quote: string; caption: string; note: string };
export type VoiceSpec = { setting: (typeof VOICE_SETTINGS)[number]; testimony: VoiceTestimony | null; coda: VoiceCoda | null };
export const voiceShape = object<VoiceSpec>({
  setting: oneOf(VOICE_SETTINGS),
  testimony: nullable(
    object<VoiceTestimony>({
      kicker: unitRef,
      kickerId: domId,
      evidence: text,
      quote: unitRef,
      credit: unitRef,
      meta: unitRef,
      echo: nullable(object<VoiceEcho>({ quote: unitRef, attribution: heldOrUnitShape }))
    })
  ),
  coda: nullable(object<VoiceCoda>({ label: text, viewBox, tile: domId, weave: domId, kicker: unitRef, quote: unitRef, caption: unitRef, note: unitRef }))
});
